"""Проставляет cache-busting версии (?v=хэш) для photos.js и banners.js в index.html.

Зачем отдельным файлом: build_photos.py правит index.html прямо во время сборки
(несколько минут). Если за это время в репозиторий успели залить свой index.html
(а ссылки с ?v= стоят в той же паре строк), то `git pull --rebase --autostash`
падает с конфликтом — автообновление кэша завершается ошибкой. Поэтому workflow
теперь: откатывает index.html к версии из репозитория -> подтягивает свежие
правки -> запускает этот скрипт, и версии ставятся уже в свежий index.html.
Скрипт идемпотентный: повторный запуск ничего не ломает.
"""
import hashlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")

def bump(html, name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print(f"  {name} не найден — версию не трогаю")
        return html
    version = hashlib.sha256(open(path, "rb").read()).hexdigest()[:10]
    pat = r'src="' + re.escape(name) + r'(?:\?v=[^"]*)?"'
    new, n = re.subn(pat, f'src="{name}?v={version}"', html, count=1)
    print(f"  {name}: ?v={version}" if n else f"  предупреждение: тег {name} в index.html не найден")
    return new

def main():
    if not os.path.exists(INDEX):
        print("index.html не найден", file=sys.stderr); return
    html = open(INDEX, "r", encoding="utf-8").read()
    new = bump(bump(html, "photos.js"), "banners.js")
    if new != html:
        open(INDEX, "w", encoding="utf-8").write(new)

if __name__ == "__main__":
    main()
