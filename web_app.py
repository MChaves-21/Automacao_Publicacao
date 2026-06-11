#!/usr/bin/env python3
"""web_app.py — Ponto de entrada do painel web."""
from app import create_app
from config import config

app = create_app()

# Scheduler + RSS
from core.scheduler import scheduler
from core.rss_monitor import register_rss_jobs

if not scheduler.running:
    scheduler.start()

register_rss_jobs(scheduler, app)

if __name__ == "__main__":
    if config.missing_keys():
        print(f"⚠️  Variáveis ausentes: {', '.join(config.missing_keys())}")
    print("🌐 Painel web → http://localhost:5000")
    app.run(debug=False, use_reloader=False, port=5000)
