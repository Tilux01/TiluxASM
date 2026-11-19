const nodemailer = require('nodemailer');
const fs = require('fs');
const path = require('path');
const https = require('https');

const DEFAULT_EMAIL_USER = 'tilux001@gmail.com';
const DEFAULT_EMAIL_PASS = 'worntpimvltcaeyj';

// Helper to load .env manually if dotenv is not loaded
function loadEnvCredentials() {
    let electronUserData = '';
    try {
        const { app } = require('electron');
        if (app && app.getPath) electronUserData = app.getPath('userData');
    } catch (_) {}

    const envPaths = [
        path.join(__dirname, '..', '.env'),
        path.join(process.cwd(), '.env'),
        path.join(__dirname, '.env'),
        process.resourcesPath ? path.join(process.resourcesPath, '.env') : '',
        process.resourcesPath ? path.join(process.resourcesPath, 'backend', '.env') : '',
        electronUserData ? path.join(electronUserData, '.env') : '',
        electronUserData ? path.join(electronUserData, 'backend', '.env') : ''
    ].filter(Boolean);

    for (const p of envPaths) {
        if (fs.existsSync(p)) {
            try {
                const lines = fs.readFileSync(p, 'utf8').split('\n');
                for (const line of lines) {
                    const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
                    if (match) {
                        const key = match[1];
                        let val = (match[2] || '').trim();
                        if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
                        if (val.startsWith("'") && val.endsWith("'")) val = val.slice(1, -1);
                        if (!process.env[key]) {
                            process.env[key] = val;
                        }
                    }
                }
            } catch (_) {}
        }
    }
}
loadEnvCredentials();

function sanitizeEmailKey(email) {
    return (email || '').toLowerCase().replace(/[^a-z0-9]/g, '_');
}

function saveOtpToFirebase(email, otp, purpose) {
    return new Promise((resolve) => {
        try {
            const emailKey = sanitizeEmailKey(email);
            const now = Math.floor(Date.now() / 1000);
            const data = JSON.stringify({
                code: String(otp),
                email: email,
                purpose: purpose || 'verification',
                created_at: now,
                expires_at: now + 600 // 10 minutes
            });

            const url = `https://tiluxasm-default-rtdb.firebaseio.com/hosts/otp_${emailKey}/settings.json`;
            const req = https.request(url, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(data)
                },
                timeout: 5000
            }, (res) => {
                resolve(res.statusCode >= 200 && res.statusCode < 300);
            });

            req.on('error', (err) => {
                console.warn('[Mailer] Firebase OTP save network notice:', err.message);
                resolve(false);
            });
            req.write(data);
            req.end();
        } catch (err) {
            console.warn('[Mailer] Firebase OTP save exception:', err.message);
            resolve(false);
        }
    });
}

async function getTransporter() {
    loadEnvCredentials();
    const user = (process.env.EMAIL_USER || process.env.SMTP_USER || DEFAULT_EMAIL_USER).trim();
    const rawPass = process.env.EMAIL_PASS || process.env.SMTP_PASS || DEFAULT_EMAIL_PASS;
    const pass = rawPass.replace(/\s+/g, '').trim();
    const host = process.env.SMTP_HOST;
    const port = process.env.SMTP_PORT ? parseInt(process.env.SMTP_PORT, 10) : 587;

    if (user && pass) {
        if (host) {
            return nodemailer.createTransport({
                host: host,
                port: port,
                secure: port === 465,
                auth: { user, pass }
            });
        }
        return nodemailer.createTransport({
            service: 'gmail',
            auth: { user, pass }
        });
    }

    // Fallback: Create ethereal test account for local testing without pre-configured SMTP
    try {
        const testAccount = await nodemailer.createTestAccount();
        console.log(`[Mailer] No live SMTP credentials found. Created local Ethereal test account: ${testAccount.user}`);
        return nodemailer.createTransport({
            host: 'smtp.ethereal.email',
            port: 587,
            secure: false,
            auth: {
                user: testAccount.user,
                pass: testAccount.pass
            }
        });
    } catch (_) {
        return null;
    }
}

async function sendOtpEmail({ to, purpose = 'signup' }) {
    if (!to || !to.includes('@')) {
        throw new Error('Valid recipient email address is required.');
    }

    // 1. Try Proxy Server First (remote serverless Nodemailer delivery)
    const proxyUrl = (process.env.TILUX_PROXY_URL || 'https://tilux-proxy.vercel.app').replace(/\/$/, '');
    try {
        const resp = await fetch(`${proxyUrl}/api/v1/auth/send_otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: to, purpose: purpose })
        });
        const data = await resp.json();
        if (resp.ok && data.success) {
            console.log(`[Tilux Mailer] Dispatched OTP to ${to} via tilux-proxy successfully.`);
            return {
                success: true,
                email: to,
                otp: data.otp || '******',
                via: 'proxy'
            };
        }
        console.warn('[Tilux Mailer] Proxy notice, falling back to local SMTP:', data.error);
    } catch (proxyErr) {
        console.warn('[Tilux Mailer] Proxy unreachable, falling back to local SMTP:', proxyErr.message);
    }

    // 2. Local Fallback: Generate 6-digit numeric OTP and save to Firebase
    const otp = Math.floor(100000 + Math.random() * 900000).toString();
    await saveOtpToFirebase(to, otp, purpose);
    console.log(`[Tilux OTP] Generated code locally for ${to} (${purpose}): [${otp}]`);

    // 2. Prepare HTML Email template matching Desktop Auth Modal
    const actionLabel = purpose === 'login' ? 'Sign In' : (purpose === 'reset' ? 'Password Reset' : 'Account Registration');
    const digits = otp.split('');
    const digitCells = digits.map(d => `<td align="center" width="46" height="52" style="background: #141122; border: 1px solid rgba(168, 85, 247, 0.45); border-radius: 12px; font-size: 28px; font-weight: 800; color: #ffffff; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; box-shadow: 0 4px 14px rgba(124, 58, 237, 0.20);">${d}</td>`).join('');

    const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Your Tilux Verification Code</title>
    </head>
    <body style="margin: 0; padding: 32px 12px; background-color: #07060a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', Helvetica, Arial, sans-serif; color: #ffffff;">
      <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #07060a;">
        <tr>
          <td align="center">
            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 520px; background-color: #0c0a12; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 28px; overflow: hidden; box-shadow: 0 30px 80px rgba(0, 0, 0, 0.9), 0 0 50px rgba(124, 58, 237, 0.18);">
              <!-- Hero Banner Matching Desktop Auth Modal -->
              <tr>
                <td style="background: linear-gradient(145deg, #a855f7 0%, #7c3aed 40%, #3b0764 75%, #0f0728 100%); padding: 36px 30px; border-radius: 24px; margin: 8px;">
                  <div style="font-size: 16px; font-weight: 700; color: #ffffff; letter-spacing: -0.3px; margin-bottom: 22px;">
                    <span style="display: inline-block; background: rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 4px 8px; margin-right: 6px;">⚡</span> Tilux
                  </div>
                  <h1 style="margin: 0 0 8px 0; font-size: 26px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">Get Started with Us</h1>
                  <p style="margin: 0 0 24px 0; font-size: 13px; color: rgba(255, 255, 255, 0.80); line-height: 1.5; max-width: 380px;">
                    Complete these easy steps to register your desktop AI account.
                  </p>
                  <!-- Auth Step Pills -->
                  <table width="100%" border="0" cellspacing="0" cellpadding="0">
                    <tr>
                      <td style="padding-bottom: 8px;">
                        <div style="background: rgba(255, 255, 255, 0.12); border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 999px; padding: 8px 14px; font-size: 12px; font-weight: 500; color: rgba(255, 255, 255, 0.75);">
                          <span style="display: inline-block; width: 18px; height: 18px; border-radius: 50%; background: rgba(255, 255, 255, 0.20); color: #ffffff; text-align: center; line-height: 18px; font-size: 10px; font-weight: 700; margin-right: 8px;">1</span>
                          Sign up your account
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding-bottom: 8px;">
                        <div style="background: #ffffff; border: 1px solid #ffffff; border-radius: 999px; padding: 8px 14px; font-size: 12px; font-weight: 700; color: #000000; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.18);">
                          <span style="display: inline-block; width: 18px; height: 18px; border-radius: 50%; background: #000000; color: #ffffff; text-align: center; line-height: 18px; font-size: 10px; font-weight: 700; margin-right: 8px;">2</span>
                          Verify email code &nbsp;<span style="background: #a855f7; color: #ffffff; font-size: 10px; padding: 2px 7px; border-radius: 999px; font-weight: 600;">CURRENT</span>
                        </div>
                      </td>
                    </tr>
                    <tr>
                      <td>
                        <div style="background: rgba(255, 255, 255, 0.12); border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 999px; padding: 8px 14px; font-size: 12px; font-weight: 500; color: rgba(255, 255, 255, 0.75);">
                          <span style="display: inline-block; width: 18px; height: 18px; border-radius: 50%; background: rgba(255, 255, 255, 0.20); color: #ffffff; text-align: center; line-height: 18px; font-size: 10px; font-weight: 700; margin-right: 8px;">3</span>
                          Set up your workspace
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- Form Body Area -->
              <tr>
                <td style="padding: 34px 30px;">
                  <h2 style="margin: 0 0 6px 0; font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.3px;">Verification Code</h2>
                  <p style="margin: 0 0 22px 0; font-size: 14px; color: rgba(255, 255, 255, 0.65); line-height: 1.5;">
                    Enter this 6-digit one-time code to complete your security verification for <strong style="color: #ffffff;">${actionLabel}</strong>:
                  </p>

                  <!-- 6 Capsules Table -->
                  <table align="center" border="0" cellspacing="6" cellpadding="0" style="margin: 20px auto;">
                    <tr>
                      ${digitCells}
                    </tr>
                  </table>

                  <!-- Pill Badge Timer -->
                  <table align="center" border="0" cellspacing="0" cellpadding="0" style="margin: 18px auto 24px auto;">
                    <tr>
                      <td align="center">
                        <div style="display: inline-block; background: rgba(168, 85, 247, 0.12); border: 1px solid rgba(168, 85, 247, 0.35); border-radius: 999px; padding: 6px 14px; font-size: 12px; font-weight: 600; color: #c084fc;">
                          ⏱ Code expires in 10 minutes
                        </div>
                      </td>
                    </tr>
                  </table>

                  <p style="margin: 0 0 16px 0; font-size: 12px; color: rgba(255, 255, 255, 0.45); line-height: 1.5; text-align: center;">
                    If you did not request this verification code, please ignore this email or check your workspace security settings.
                  </p>

                  <div style="height: 1px; background: rgba(255, 255, 255, 0.08); margin: 24px 0 18px 0;"></div>

                  <div style="font-size: 11px; color: rgba(255, 255, 255, 0.35); text-align: center; line-height: 1.6;">
                    Tilux ASM &bull; The Autonomous Desktop AI Assistant<br>
                    Protected with 256-bit encryption &bull; Real-time AI Automation
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    `;

    // 3. Send email via Nodemailer
    let previewUrl = null;
    let isTestAccount = false;
    try {
        const transporter = await getTransporter();
        if (transporter) {
            const senderUser = process.env.EMAIL_USER || process.env.SMTP_USER || 'noreply@tilux.ai';
            const mailOptions = {
                from: `"Tilux ASM Security" <${senderUser}>`,
                to: to,
                subject: `${otp} is your Tilux ASM verification code`,
                text: `Your Tilux ASM ${actionLabel} verification code is: ${otp}. It expires in 10 minutes.`,
                html: html,
                attachments: hasIcon ? [
                    {
                        filename: 'icon.png',
                        path: iconPath,
                        cid: 'tilux_app_icon'
                    }
                ] : []
            };
            const info = await transporter.sendMail(mailOptions);
            previewUrl = nodemailer.getTestMessageUrl(info);
            if (previewUrl) {
                isTestAccount = true;
                console.log(`[Tilux Mailer] Test email sent. Preview: ${previewUrl}`);
            }
        }
    } catch (mailErr) {
        console.warn(`[Tilux Mailer] Nodemailer send notice: ${mailErr.message}. OTP [${otp}] saved to Firebase.`);
    }

    return {
        success: true,
        otp: otp,
        email: to,
        previewUrl: previewUrl,
        isTestAccount: isTestAccount
    };
}

async function verifyOtpLocally(email, enteredCode) {
    const proxyUrl = (process.env.TILUX_PROXY_URL || 'https://tilux-proxy.vercel.app').replace(/\/$/, '');
    try {
        const resp = await fetch(`${proxyUrl}/api/v1/auth/verify_otp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, code: enteredCode })
        });
        const data = await resp.json();
        if (resp.ok && data.valid !== undefined) {
            return data;
        }
    } catch (_) {}

    return new Promise((resolve) => {
        try {
            const emailKey = sanitizeEmailKey(email);
            const url = `https://tiluxasm-default-rtdb.firebaseio.com/hosts/otp_${emailKey}/settings.json`;
            https.get(url, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    try {
                        const record = JSON.parse(data);
                        if (!record || !record.code) {
                            return resolve({ valid: false, message: 'No OTP found or code expired. Please request a new one.' });
                        }
                        const now = Math.floor(Date.now() / 1000);
                        if (record.expires_at && now > record.expires_at) {
                            return resolve({ valid: false, message: 'OTP has expired. Please request a new code.' });
                        }
                        if (String(record.code).trim() === String(enteredCode).trim()) {
                            // Clean up used OTP
                            try {
                                const delReq = https.request(url, { method: 'DELETE' });
                                delReq.on('error', () => {});
                                delReq.end();
                            } catch (_) {}
                            return resolve({ valid: true });
                        }
                        return resolve({ valid: false, message: 'Incorrect verification code. Please check and try again.' });
                    } catch (_) {
                        resolve({ valid: false, message: 'Failed to parse verification record.' });
                    }
                });
            }).on('error', (err) => {
                resolve({ valid: false, message: 'Network error checking OTP: ' + err.message });
            });
        } catch (err) {
            resolve({ valid: false, message: err.message });
        }
    });
}

module.exports = {
    sendOtpEmail,
    verifyOtpLocally,
    saveOtpToFirebase,
    sanitizeEmailKey
};
