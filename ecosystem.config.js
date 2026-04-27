// PM2 process manager config for the ULOV+ backend.
//
// Usage on the prod server:
//   cd /var/www/workers/ulov/backend
//   pm2 start ecosystem.config.js          # boot both processes
//   pm2 save                                # persist for boot
//   pm2 startup systemd                     # generate systemd unit
//   pm2 reload ecosystem.config.js          # zero-downtime reload
//
// Pydantic loads `.env` automatically from the working directory, so we
// don't need to pass env vars here — keep secrets in `.env` next to this
// file (chmod 600). PM2 inherits the parent shell's PATH; the `interpreter`
// is set to "none" so PM2 execs the venv binaries directly.

const path = require('path');

const CWD = __dirname;
const VENV = path.join(CWD, 'venv', 'bin');
const LOG_DIR = '/var/log/pm2';

module.exports = {
  apps: [
    {
      name: 'ulov-api',
      cwd: CWD,
      script: path.join(VENV, 'uvicorn'),
      args: [
        'app.main:app',
        '--host', '127.0.0.1',
        '--port', '8499',
        '--proxy-headers',
        '--forwarded-allow-ips', '*',
        '--workers', '2',
      ].join(' '),
      interpreter: 'none',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '15s',
      max_memory_restart: '1G',
      kill_timeout: 8000,
      out_file: `${LOG_DIR}/ulov-api.out.log`,
      error_file: `${LOG_DIR}/ulov-api.err.log`,
      merge_logs: true,
      time: true,
    },
    {
      name: 'ulov-worker',
      cwd: CWD,
      script: path.join(VENV, 'arq'),
      args: 'app.workers.arq_worker.WorkerSettings',
      interpreter: 'none',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '15s',
      max_memory_restart: '512M',
      kill_timeout: 5000,
      out_file: `${LOG_DIR}/ulov-worker.out.log`,
      error_file: `${LOG_DIR}/ulov-worker.err.log`,
      merge_logs: true,
      time: true,
    },
  ],
};
