module.exports = {
  apps: [{
    name: 'ai-publish-engine',
    cwd: '/var/www/ai-publish-engine',
    script: '/var/www/ai-publish-engine/run.py',
    interpreter: '/var/www/ai-publish-engine/venv/bin/python3',
    instances: 1,
    exec_mode: 'fork',
    env: {
      PYTHONPATH: '/var/www/ai-publish-engine',
      PORT: '9109',
      LOG_LEVEL: 'info',
      OUTPUT_DIR: '/var/www/ai-publish-engine/outputs',
      JOB_FILE: '/var/www/ai-publish-engine/jobs/jobs.json',
    },
    max_memory_restart: '1G',
    error_file: '/var/www/ai-publish-engine/logs/err.log',
    out_file: '/var/www/ai-publish-engine/logs/out.log',
    merge_logs: true,
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    max_restarts: 10,
    restart_delay: 3000,
    watch: false,
  }]
}
