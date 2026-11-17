const nodemailer = require('nodemailer');
const fs = require('fs');
const path = require('path');
const https = require('https');

// Helper to load .env manually if dotenv is not loaded
function loadEnvCredentials() {
    const envPaths = [
        path.join(__dirname, '..', '.env'),
        path.join(process.cwd(), '.env'),
        path.join(__dirname, '.env')
    ];
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
    const user = process.env.EMAIL_USER || process.env.SMTP_USER;
    const pass = process.env.EMAIL_PASS || process.env.SMTP_PASS;
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

    // Generate 6-digit numeric OTP
    const otp = Math.floor(100000 + Math.random() * 900000).toString();

    // 1. Save to Firebase Realtime Database
    await saveOtpToFirebase(to, otp, purpose);
    console.log(`[Tilux OTP] Generated code for ${to} (${purpose}): [${otp}]`);

    // 2. Prepare HTML Email template
    const actionLabel = purpose === 'login' ? 'Sign In' : 'Account Registration';
    const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Your Tilux Verification Code</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #07060a; color: #ffffff; margin: 0; padding: 24px; }
        .card { max-width: 480px; margin: 0 auto; background: #0f0d15; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; padding: 36px 32px; box-shadow: 0 20px 40px rgba(0,0,0,0.6); }
        .logo { font-size: 20px; font-weight: 700; color: #c084fc; margin-bottom: 20px; display: flex; align-items: center; gap: 8px; }
        h2 { font-size: 22px; margin: 0 0 10px 0; color: #ffffff; }
        p { font-size: 14px; line-height: 1.6; color: #a1a1aa; margin: 0 0 24px 0; }
        .otp-box { background: rgba(168, 85, 247, 0.1); border: 1px solid #a855f7; border-radius: 12px; padding: 18px 24px; text-align: center; margin: 24px 0; }
        .otp-code { font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #ffffff; font-family: monospace; }
        .footer { font-size: 12px; color: #71717a; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 18px; margin-top: 24px; }
      </style>
    </head>
    <body>
      <div class="card">
        <div class="logo">✦ Tilux AI</div>
        <h2>Verification Code</h2>
        <p>You requested a one-time verification code for <strong>${actionLabel}</strong> on your Tilux desktop workspace.</p>
        <div class="otp-box">
          <div class="otp-code">${otp}</div>
        </div>
        <p>This code will expire in <strong>10 minutes</strong>. If you did not make this request, you can safely ignore this email.</p>
        <div class="footer">
          &copy; ${new Date().getFullYear()} Tilux ASM. All rights reserved.
        </div>
      </div>
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
            const info = await transporter.sendMail({
                from: `"Tilux AI Security" <${senderUser}>`,
                to: to,
                subject: `${otp} is your Tilux verification code`,
                text: `Your Tilux ${actionLabel} verification code is: ${otp}. It expires in 10 minutes.`,
                html: html
            });
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

function verifyOtpLocally(email, enteredCode) {
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
