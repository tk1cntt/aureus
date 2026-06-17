/**
 * Test script for Aureus Gateway
 * Tests TCP connection and data sending to gateway
 *
 * Usage: node test-gateway.js [host] [port] "json_message"
 *   - host: default "localhost"
 *   - port: default 5556 (TCP) or 5555 (ZMQ PULL - not tested here)
 *   - json_message: optional JSON message to send
 */

const net = require('net');

const HOST = process.env.GATEWAY_HOST || 'localhost';
const PORT = parseInt(process.env.GATEWAY_PORT, 10) || 5556;

console.log('='.repeat(70));
console.log('Aureus Gateway Test Client');
console.log('='.repeat(70));
console.log(`Target: ${HOST}:${PORT}`);
console.log('');

// Test message templates
const messages = {
  tick: JSON.stringify({
    type: 'TICK',
    symbol: 'EURUSD',
    t: Date.now(),
    bid: 1.0850,
    ask: 1.0852,
    vol: 1.5
  }),

  candle: JSON.stringify({
    type: 'CANDLE',
    symbol: 'GBPUSD',
    t: Date.now() - 3600000,
    o: 1.2650,
    h: 1.2680,
    l: 1.2640,
    c: 1.2670,
    v: 125000,
    tf: 'M15'
  }),

  orderOpened: JSON.stringify({
    type: 'ORDER_OPENED',
    cmd_id: 'TEST-001',
    symbol: 'XAUUSD',
    ticket: 123456,
    direction: 'BUY',
    order_type: 'MARKET',
    volume: 0.1,
    open_price: 2650.00,
    sl: 2600.00,
    tp: 2700.00,
    magic: 12345,
    strategy_name: 'TestStrategy',
    trace_id: 'trace-001',
    open_time: Date.now(),
    t: Date.now()
  })
};

async function connectAndSend(message, label) {
  return new Promise((resolve, reject) => {
    const client = net.createConnection({ host: HOST, port: PORT }, () => {
      console.log(`✓ Connected to ${HOST}:${PORT}`);
      console.log(`Sending ${label}:`);
      console.log('  ' + JSON.stringify(JSON.parse(message), null, 2));

      client.write(message + '\n'); // Gateway expects newline-delimited JSON

      // Wait 3s so gateway has time to read and process the message
      setTimeout(() => {
        client.end();
      }, 3000);
    });

    client.on('data', (data) => {
      console.log(`Server sent: ${data.toString().trim()}`);
    });

    client.on('end', () => {
      console.log('✓ Connection closed');
      resolve(true);
    });

    client.on('error', (error) => {
      console.error(`✗ Error:`, error.message);
      if (error.code === 'ECONNREFUSED') {
        console.error('');
        console.error('Gateway is NOT accepting connections!');
        console.error('Possible causes:');
        console.error('  1. aureus-gateway Docker container is not running');
        console.error('  2. Firewall blocking port ' + PORT);
        console.error('  3. Wrong host/port configuration');
        console.error('');
        console.error('Check with:');
        console.error(`  wsl -d Aureus -e bash -lc "docker ps | grep aureus-gateway"`);
        console.error('');
        console.error('Start gateway with:');
        console.error(`  wsl -d Aureus -e bash -lc "cd /mnt/d/Aureus && ./scripts/dev-service.sh"`);
      }
      reject(error);
    });
  });
}

async function runTests() {
  const results = {
    connected: false,
    testsPassed: 0,
    testsFailed: 0
  };

  console.log('-'.repeat(70));
  console.log('Step 1: Connecting to Gateway...');
  console.log('-'.repeat(70));

  try {
    await connectAndSend(messages.tick, 'TICK Message');
    results.connected = true;
    results.testsPassed++;

    console.log('');
    console.log('-'.repeat(70));
    console.log('Step 2: Testing CANDLE Message...');
    console.log('-'.repeat(70));

    await connectAndSend(messages.candle, 'CANDLE Message');
    results.testsPassed++;

    console.log('');
    console.log('-'.repeat(70));
    console.log('Step 3: Testing ORDER_OPENED Message...');
    console.log('-'.repeat(70));

    await connectAndSend(messages.orderOpened, 'ORDER_OPENED Message');
    results.testsPassed++;

  } catch (error) {
    results.testsFailed++;
  }

  console.log('');
  console.log('='.repeat(70));
  console.log('Test Summary');
  console.log('='.repeat(70));
  console.log(`Connected: ${results.connected ? 'YES ✓' : 'NO ✗'}`);
  console.log(`Tests Passed: ${results.testsPassed}`);
  console.log(`Tests Failed: ${results.testsFailed}`);
  console.log('='.repeat(70));

  if (!results.connected) {
    console.log('');
    console.log('⚠️  Gateway is not accepting connections.');
    console.log('Please start the gateway service and re-run this test.');
    process.exit(1);
  }

  process.exit(results.testsFailed > 0 ? 1 : 0);
}

runTests();
