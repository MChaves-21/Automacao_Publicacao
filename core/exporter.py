"""core/exporter.py — Geração de relatórios CSV e PDF."""
import csv
import io
from datetime import datetime
from typing import Optional


def export_posts_csv(posts: list) -> bytes:
    """
    Exporta lista de posts como CSV.
    Recebe dicts com os campos do Post.to_dict().
    """
    buf = io.StringIO()
    fields = ["id", "author", "status", "platforms", "content",
              "scheduled_at", "published_at", "ab_variant", "created_at"]

    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()

    for p in posts:
        row = {
            "id":           p.get("id"),
            "author":       (p.get("author") or {}).get("username", ""),
            "status":       p.get("status", ""),
            "platforms":    "|".join(p.get("platforms") or []),
            "content":      (p.get("content") or "").replace("\n", " ")[:300],
            "scheduled_at": p.get("scheduled_at", ""),
            "published_at": p.get("published_at", ""),
            "ab_variant":   p.get("ab_variant", ""),
            "created_at":   p.get("created_at", ""),
        }
        writer.writerow(row)

    return buf.getvalue().encode("utf-8-sig")  # BOM para Excel


def export_report_html(stats: dict, posts: list, log_entries: list) -> str:
    """
    Gera um relatório HTML completo e estilizado,
    pronto para impressão ou conversão em PDF via browser.
    """
    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
    total   = stats.get("sessions", 0)
    pub     = stats.get("published", 0)
    errors  = stats.get("errors", 0)
    pending = stats.get("pending", 0)

    by_plat = stats.get("by_platform", {})
    plat_rows = "".join(
        f"<tr><td>{p}</td><td>{n}</td></tr>"
        for p, n in by_plat.items()
    )

    recent_rows = "".join(
        f"""<tr>
          <td>{(p.get('created_at') or '')[:10]}</td>
          <td>{(p.get('author') or {}).get('username','—')}</td>
          <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            {(p.get('content') or '')[:80]}
          </td>
          <td>{'|'.join(p.get('platforms') or [])}</td>
          <td style="color:{'#22d47a' if p.get('status')=='published' else '#f0a020'}">
            {p.get('status','—')}
          </td>
        </tr>"""
        for p in posts[:30]
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório de Marketing — {now}</title>
<style>
  body{{font-family:'Segoe UI',sans-serif;color:#1a1a2e;max-width:1100px;margin:0 auto;padding:32px}}
  h1{{font-size:24px;margin-bottom:4px}}
  .sub{{color:#666;font-size:13px;margin-bottom:32px}}
  .cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}}
  .card{{background:#f8f9fa;border-radius:12px;padding:20px;text-align:center}}
  .card-n{{font-size:36px;font-weight:700;margin-bottom:4px}}
  .card-l{{font-size:12px;color:#666;text-transform:uppercase;letter-spacing:.04em}}
  .green{{color:#22d47a}}.amber{{color:#f0a020}}.red{{color:#f05060}}.blue{{color:#4a8fff}}
  table{{width:100%;border-collapse:collapse;margin-bottom:32px}}
  th{{background:#f0f0f0;padding:10px 12px;text-align:left;font-size:12px;
      text-transform:uppercase;letter-spacing:.04em}}
  td{{padding:9px 12px;border-bottom:1px solid #eee;font-size:13px}}
  h2{{font-size:16px;margin:28px 0 12px;border-bottom:2px solid #f0a020;padding-bottom:6px}}
  @media print{{body{{padding:16px}}.no-print{{display:none}}}}
</style>
</head>
<body>
<button class="no-print" onclick="window.print()"
  style="float:right;padding:8px 16px;background:#f0a020;color:#07090d;
         border:none;border-radius:8px;cursor:pointer;font-weight:600">
  🖨️ Imprimir / Salvar PDF
</button>
<h1>📣 Relatório de Marketing</h1>
<div class="sub">Gerado em {now} · Marketing Automation System</div>

<div class="cards">
  <div class="card"><div class="card-n green">{pub}</div><div class="card-l">Publicados</div></div>
  <div class="card"><div class="card-n amber">{pending}</div><div class="card-l">Pendentes</div></div>
  <div class="card"><div class="card-n blue">{total}</div><div class="card-l">Sessões</div></div>
  <div class="card"><div class="card-n red">{errors}</div><div class="card-l">Erros</div></div>
</div>

<h2>Por plataforma</h2>
<table>
  <thead><tr><th>Plataforma</th><th>Posts publicados</th></tr></thead>
  <tbody>{plat_rows or '<tr><td colspan="2" style="color:#999">Sem dados</td></tr>'}</tbody>
</table>

<h2>Posts recentes</h2>
<table>
  <thead><tr><th>Data</th><th>Autor</th><th>Conteúdo</th><th>Plataformas</th><th>Status</th></tr></thead>
  <tbody>{recent_rows or '<tr><td colspan="5" style="color:#999">Sem posts</td></tr>'}</tbody>
</table>

<div style="text-align:center;color:#999;font-size:11px;margin-top:32px">
  Marketing Automation System · Relatório gerado automaticamente
</div>
</body>
</html>"""
