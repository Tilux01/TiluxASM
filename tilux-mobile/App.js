import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet, Text, View, TextInput, TouchableOpacity, FlatList,
  SafeAreaView, StatusBar, ActivityIndicator, Alert, Modal, Platform,
  KeyboardAvoidingView, ScrollView, Keyboard
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { CameraView, useCameraPermissions } from 'expo-camera';
import io from 'socket.io-client';

export default function App() {
  const [paired, setPaired] = useState(false);
  const [serverUrl, setServerUrl] = useState('');
  const [token, setToken] = useState('');
  const [pcName, setPcName] = useState('Tilux-PC');
  const [statusText, setStatusText] = useState('Disconnected');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showScanner, setShowScanner] = useState(false);

  const socketRef = useRef(null);
  const scanLock = useRef(false);
  const listRef = useRef(null);
  const [permission, requestPermission] = useCameraPermissions();

  useEffect(() => {
    loadSavedConnection();
  }, []);

  const loadSavedConnection = async () => {
    try {
      const savedUrl = await AsyncStorage.getItem('tilux_url');
      const savedToken = await AsyncStorage.getItem('tilux_token');
      if (savedUrl && savedToken) {
        setServerUrl(savedUrl);
        setToken(savedToken);
        connectSocket(savedUrl, savedToken);
      }
    } catch (e) {
      console.log('Failed to load connection', e);
    }
  };

  const normalizeUrl = (rawUrl) => {
    let clean = (rawUrl || '').trim();
    if (!clean) return '';
    clean = clean.replace(/^(wss?:\/\/|https?:\/\/)/i, '');
    clean = clean.replace(/\/+$/, '');
    if (!clean.includes(':')) clean = clean + ':8932';
    return 'http://' + clean;
  };

  const connectSocket = (url, connToken) => {
    if (socketRef.current) socketRef.current.disconnect();

    const targetUrl = normalizeUrl(url);
    setServerUrl(targetUrl);

    const socket = io(targetUrl, {
      transports: ['polling', 'websocket'],
      reconnection: true,
      reconnectionAttempts: 10,
      timeout: 10000
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      setStatusText('Connecting...');
      socket.emit('pair_device', { token: connToken });
    });
    socket.on('connect_error', () => setStatusText('Connection Error'));
    socket.on('paired', (data) => {
      if (data.status === 'success') {
        setPaired(true);
        setStatusText('Connected: ' + (data.pc_name || 'Tilux-PC'));
        setPcName(data.pc_name || 'Tilux-PC');
        AsyncStorage.setItem('tilux_url', targetUrl);
        AsyncStorage.setItem('tilux_token', connToken);
      } else {
        Alert.alert('Pairing Failed', 'Invalid token or unauthorized PC connection.');
        setStatusText('Unauthorized');
      }
    });
    socket.on('agent_status', () => setLoading(true));
    socket.on('agent_reply', (data) => {
      setLoading(false);
      if (data.reply) setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'ai', text: data.reply }]);
    });
    socket.on('disconnect', () => {
      setStatusText('Disconnected');
      setPaired(false);
    });
  };

  const handleManualPair = () => {
    Keyboard.dismiss();
    if (!serverUrl || !token) {
      Alert.alert('Error', 'Please enter PC Server URL and Pairing Token.');
      return;
    }
    const fixedUrl = normalizeUrl(serverUrl);
    setServerUrl(fixedUrl);
    connectSocket(fixedUrl, token);
  };

  const openScanner = async () => {
    scanLock.current = false;
    if (Platform.OS === 'web') {
      const secure = typeof window !== 'undefined' && window.isSecureContext;
      if (!secure) {
        Alert.alert('Camera Blocked in Browser', 'Browsers only allow the camera on HTTPS or localhost. Open the app in Expo Go instead, or enter the URL and token manually.');
        return;
      }
    }
    if (!permission || !permission.granted) {
      const res = await requestPermission();
      if (!res || !res.granted) {
        Alert.alert('Camera Permission Needed', 'Allow camera access to scan the pairing QR code.');
        return;
      }
    }
    setShowScanner(true);
  };

  const handleBarcodeScanned = ({ data }) => {
    if (scanLock.current) return;
    scanLock.current = true;
    let url = '', tok = '', name = '';
    try {
      const obj = JSON.parse(data);
      url = obj.url || obj.server || obj.serverUrl || '';
      tok = obj.token || obj.pair_token || obj.pairToken || '';
      name = obj.pc_name || obj.pcName || '';
    } catch (e) {
      const urlMatch = data.match(/(https?:\/\/[^\s"'<>]+)/i);
      if (urlMatch) url = urlMatch[1];
      const tokMatch = data.match(/token=([^&\s"']+)/i);
      if (tokMatch) tok = tokMatch[1];
    }
    setShowScanner(false);
    if (url && tok) {
      if (name) setPcName(name);
      setServerUrl(url);
      setToken(tok);
      setTimeout(() => connectSocket(url, tok), 300);
    } else if (url) {
      setServerUrl(url);
      Alert.alert('URL Scanned', 'Got the PC address but no token. Enter the Pair Token and tap Connect.');
    } else {
      Alert.alert('Invalid QR', 'That QR code is not a Tilux pairing code.');
      scanLock.current = false;
    }
  };

  const sendPrompt = () => {
    if (!prompt.trim() || !socketRef.current) return;
    const userText = prompt.trim();
    setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'user', text: userText }]);
    setPrompt('');
    setLoading(true);
    socketRef.current.emit('send_prompt', { text: userText, token: token });
  };

  const disconnect = () => {
    if (socketRef.current) socketRef.current.disconnect();
    AsyncStorage.multiRemove(['tilux_url', 'tilux_token']);
    setPaired(false);
    setMessages([]);
    setStatusText('Disconnected');
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
    >
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor="#0B0E14" />

        <View style={styles.header}>
          <Text style={styles.title}>TILUX <Text style={styles.titleAccent}>REMOTE</Text></Text>
          <View style={[styles.badge, paired ? styles.badgeOn : styles.badgeOff]}>
            <View style={[styles.dot, paired ? styles.dotOn : styles.dotOff]} />
            <Text style={styles.badgeText} numberOfLines={1}>{statusText}</Text>
          </View>
        </View>

        {!paired ? (
          <ScrollView
            contentContainerStyle={styles.pairScroll}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <View style={styles.card}>
              <Text style={styles.pairTitle}>Pair with Tilux PC</Text>
              <Text style={styles.pairSub}>
                Scan the QR code shown in the Tilux window on your PC, or enter the details manually.
              </Text>

              <TouchableOpacity style={styles.scanButton} onPress={openScanner}>
                <Text style={styles.scanButtonText}>SCAN QR CODE</Text>
              </TouchableOpacity>
              {Platform.OS === 'web' ? (
                <Text style={styles.webHint}>
                  Browsers need HTTPS for the camera. Open this app in Expo Go for scanning.
                </Text>
              ) : null}

              <View style={styles.divider}>
                <View style={styles.divLine} />
                <Text style={styles.divText}>OR MANUAL</Text>
                <View style={styles.divLine} />
              </View>

              <Text style={styles.label}>PC SERVER URL</Text>
              <TextInput
                style={styles.input}
                placeholder="http://192.168.1.100:8932"
                placeholderTextColor="#64748B"
                value={serverUrl}
                onChangeText={setServerUrl}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
              />

              <Text style={styles.label}>PAIRING TOKEN</Text>
              <TextInput
                style={styles.input}
                placeholder="pair_tilux_xxxxxxxx"
                placeholderTextColor="#64748B"
                value={token}
                onChangeText={setToken}
                autoCapitalize="none"
                autoCorrect={false}
              />

              <TouchableOpacity style={styles.connectButton} onPress={handleManualPair}>
                <Text style={styles.connectButtonText}>Connect to PC</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>
        ) : (
          <View style={styles.chat}>
            <FlatList
              ref={listRef}
              data={messages}
              keyExtractor={item => item.id}
              keyboardShouldPersistTaps="handled"
              onContentSizeChange={() => listRef.current && listRef.current.scrollToEnd({ animated: true })}
              renderItem={({ item }) => (
                <View style={[styles.bubble, item.sender === 'user' ? styles.userBubble : styles.aiBubble]}>
                  <Text style={styles.bubbleText}>{item.text}</Text>
                </View>
              )}
              ListEmptyComponent={
                <Text style={styles.emptyText}>
                  Connected to {pcName}. Ask Tilux to control this PC.
                </Text>
              }
              contentContainerStyle={styles.messageList}
            />

            {loading && (
              <View style={styles.loadingRow}>
                <ActivityIndicator size="small" color="#00F2FE" />
                <Text style={styles.loadingText}>Tilux is processing on PC...</Text>
              </View>
            )}

            <View style={styles.inputDock}>
              <TextInput
                style={styles.chatInput}
                placeholder="Ask Tilux to control PC..."
                placeholderTextColor="#64748B"
                value={prompt}
                onChangeText={setPrompt}
                onSubmitEditing={sendPrompt}
                multiline={false}
                returnKeyType="send"
                blurOnSubmit={false}
              />
              <TouchableOpacity style={styles.sendButton} onPress={sendPrompt}>
                <Text style={styles.sendButtonText}>&gt;</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity onPress={disconnect} style={styles.disconnectRow}>
              <Text style={styles.disconnectText}>Disconnect</Text>
            </TouchableOpacity>
          </View>
        )}
      </SafeAreaView>

      <Modal visible={showScanner} animationType="slide" onRequestClose={() => setShowScanner(false)}>
        <View style={styles.scannerContainer}>
          <CameraView
            style={StyleSheet.absoluteFillObject}
            facing="back"
            barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
            onBarcodeScanned={showScanner ? handleBarcodeScanned : undefined}
          />
          <View style={styles.scanOverlay} pointerEvents="box-none">
            <View style={styles.scanFrame} />
            <Text style={styles.scanHint}>Point at the QR code on your Tilux PC</Text>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setShowScanner(false)}>
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0B0E14' },
  container: { flex: 1, backgroundColor: '#0B0E14' },

  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: '#1E293B',
  },
  title: { fontSize: 18, fontWeight: '800', color: '#FFFFFF', letterSpacing: 1 },
  titleAccent: { color: '#00F2FE' },
  badge: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 20, maxWidth: 180,
  },
  badgeOn: { backgroundColor: 'rgba(16,185,129,0.15)', borderWidth: 1, borderColor: 'rgba(16,185,129,0.4)' },
  badgeOff: { backgroundColor: 'rgba(239,68,68,0.15)', borderWidth: 1, borderColor: 'rgba(239,68,68,0.4)' },
  dot: { width: 6, height: 6, borderRadius: 3, marginRight: 6 },
  dotOn: { backgroundColor: '#10B981' },
  dotOff: { backgroundColor: '#EF4444' },
  badgeText: { fontSize: 12, color: '#E2E8F0', fontWeight: '600', flexShrink: 1 },

  pairScroll: { flexGrow: 1, justifyContent: 'center', padding: 20 },
  card: { backgroundColor: '#111827', borderRadius: 20, padding: 22, borderWidth: 1, borderColor: '#1F2937' },
  pairTitle: { fontSize: 22, fontWeight: '700', color: '#FFFFFF', textAlign: 'center' },
  pairSub: { fontSize: 13, color: '#94A3B8', textAlign: 'center', marginTop: 8, marginBottom: 20, lineHeight: 18 },
  scanButton: { backgroundColor: '#00F2FE', borderRadius: 14, paddingVertical: 17, alignItems: 'center' },
  scanButtonText: { color: '#0B0E14', fontSize: 15, fontWeight: '800', letterSpacing: 1 },
  webHint: { color: '#F59E0B', fontSize: 11, textAlign: 'center', marginTop: 10, lineHeight: 15 },
  divider: { flexDirection: 'row', alignItems: 'center', marginVertical: 20 },
  divLine: { flex: 1, height: 1, backgroundColor: '#1F2937' },
  divText: { color: '#475569', fontSize: 10, fontWeight: '700', letterSpacing: 1, marginHorizontal: 10 },
  label: { color: '#64748B', fontSize: 10, fontWeight: '700', letterSpacing: 1, marginBottom: 6, marginTop: 4 },
  input: {
    backgroundColor: '#0B0E14', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 13,
    color: '#FFFFFF', fontSize: 14, borderWidth: 1, borderColor: '#334155', marginBottom: 12,
  },
  connectButton: { backgroundColor: '#0284C7', borderRadius: 14, paddingVertical: 16, alignItems: 'center', marginTop: 6 },
  connectButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700' },

  chat: { flex: 1 },
  messageList: { padding: 16, flexGrow: 1 },
  emptyText: { color: '#475569', fontSize: 13, textAlign: 'center', marginTop: 40, lineHeight: 19 },
  bubble: { maxWidth: '82%', padding: 13, borderRadius: 16, marginBottom: 10 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: '#0284C7', borderBottomRightRadius: 4 },
  aiBubble: { alignSelf: 'flex-start', backgroundColor: '#1E293B', borderWidth: 1, borderColor: '#334155', borderBottomLeftRadius: 4 },
  bubbleText: { color: '#FFFFFF', fontSize: 14, lineHeight: 20 },
  loadingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 8 },
  loadingText: { color: '#00F2FE', fontSize: 12, marginLeft: 8 },

  inputDock: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingTop: 10, paddingBottom: 10,
    borderTopWidth: 1, borderTopColor: '#1E293B', backgroundColor: '#0B0E14',
  },
  chatInput: {
    flex: 1, backgroundColor: '#1E293B', borderRadius: 24, paddingHorizontal: 18, paddingVertical: 12,
    color: '#FFFFFF', fontSize: 14, marginRight: 10, borderWidth: 1, borderColor: '#334155',
  },
  sendButton: { width: 46, height: 46, borderRadius: 23, backgroundColor: '#00F2FE', alignItems: 'center', justifyContent: 'center' },
  sendButtonText: { color: '#0B0E14', fontSize: 18, fontWeight: 'bold' },
  disconnectRow: { alignItems: 'center', paddingBottom: 8 },
  disconnectText: { color: '#64748B', fontSize: 12, textDecorationLine: 'underline' },

  scannerContainer: { flex: 1, backgroundColor: '#000' },
  scanOverlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  scanFrame: { width: 240, height: 240, borderWidth: 3, borderColor: '#00F2FE', borderRadius: 16 },
  scanHint: { color: '#FFFFFF', fontSize: 14, marginTop: 24, fontWeight: '600' },
  cancelButton: { marginTop: 40, paddingHorizontal: 32, paddingVertical: 12, borderRadius: 24, backgroundColor: 'rgba(255,255,255,0.15)' },
  cancelButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700' },
});
