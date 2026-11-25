## 1. Tasks

- [x] filter `record_id` в `/record`: повтор известного ключа — `duplicate`, без строки цепочки
- [x] shop очередь записей эпизода, доставка по порядку с ретраем; статус `error`/409 убраны
- [x] shop `/reset` и `/snapshot/restore` дожимают очередь, иначе 503
- [x] shop `raw.events` — дельта хода
- [x] docs `docs/api.md` (shop /turn, filter /record)
- [x] tests отказ filter посреди эпизода: ход в очереди, restore 503, после подъёма записи по порядку без дублей и повторов событий; идемпотентность filter; смок зелёный
