import sqlite3
import time
import requests
from bs4 import BeautifulSoup

url = 'https://github.com/orgs/google/repositories'
response = requests.get(url)

# 1. SQLiteデータベースの作成・接続とテーブル作成
conn = sqlite3.connect('google_repos.db')
cur = conn.cursor()

cur.execute('DROP TABLE IF EXISTS repositories')
cur.execute('''
    CREATE TABLE repositories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        language TEXT,
        stars TEXT
    )
''')
conn.commit()

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}
exclude_paths = {'repositories', 'people', 'projects', 'packages', 'sponsors', 'settings', 'teams'}

# 2. 1ページ目から最終ページまで全件スクレイピング
page = 1
retry_count = 0

while True:
    if page == 1:
        res = response
    else:
        time.sleep(1)  # サーバー負荷軽減のため1秒待機
        res = requests.get(f'{url}?page={page}', headers=headers)

    # アクセス制限（429）が出た場合は10秒待って同じページを再試行
    if res.status_code == 429:
        retry_count += 1
        if retry_count > 5:
            print(f'{page}ページ目で制限が解除されないため終了します')
            break
        print(f'{page}ページ目でアクセス制限検知。10秒待機して再試行します...')
        time.sleep(10)
        continue

    if res.status_code != 200:
        print(f'{page}ページ目で終了（ステータスコード: {res.status_code}）')
        break

    retry_count = 0
    soup = BeautifulSoup(res.text, 'html.parser')
    seen_names = set()
    saved_in_page = 0

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].split('?')[0].split('#')[0]
        parts = href.strip('/').split('/')

        if len(parts) != 2 or parts[0] != 'google' or parts[1] in exclude_paths:
            continue

        name = a_tag.get_text(strip=True)
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        parent = a_tag.find_parent('li') or a_tag.parent.parent

        stars_tag = parent.select_one('a[href$="/stargazers"]') if parent else None
        stars = stars_tag.get_text(strip=True) if stars_tag else '0'

        language = 'None'
        if parent:
            lang_tag = parent.select_one('[itemprop="programmingLanguage"]')
            if not lang_tag:
                color_dot = parent.select_one('span[style*="background-color"]')
                if color_dot:
                    lang_tag = color_dot.find_next_sibling('span') or color_dot.parent
            if lang_tag:
                language = lang_tag.get_text(strip=True) or 'None'

        cur.execute(
            'INSERT INTO repositories (name, language, stars) VALUES (?, ?, ?)',
            (name, language, stars)
        )
        saved_in_page += 1

    # 1ページごとに保存を確定
    conn.commit()

    # データが0件のページに到達したら全件取得完了
    if saved_in_page == 0:
        print(f'{page}ページ目にデータがないため全件取得を完了しました')
        break

    print(f'{page}ページ目完了（{saved_in_page}件取得）')
    page += 1

# 3. 保存したデータをSELECT文で取得して表示
cur.execute('SELECT * FROM repositories')
rows = cur.fetchall()
print(f'合計保存件数: {len(rows)} 件')
for row in rows:
    print(row)

conn.close()