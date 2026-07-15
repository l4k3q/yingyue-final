from app.models.db import get_connection

with get_connection() as conn:
    cursor = conn.execute('SELECT * FROM watch_sources')
    rows = cursor.fetchall()
    print('采集源总数:', len(rows))
    for row in rows:
        r = dict(row)
        print(f"ID: {r['id']}, 名称: {r['name']}, 启用状态: {r['status']}")

from app.models.watch import WatchSourceRepository
enabled = WatchSourceRepository.get_enabled_sources()
print('\n启用的采集源:', len(enabled))
for s in enabled:
    print(f"ID: {s['id']}, 名称: {s['name']}")
