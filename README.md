# Игровые правила для Tachyon

Набор адресов AWS EC2 и Global Accelerator всех регионов для проверки игрового UDP-трафика. Это список облачных подсетей, а не точный перечень игровых серверов: он включает также неигровые сервисы AWS.

## Файлы

- [`games/aws-udp.srs`](games/aws-udp.srs) — готовый бинарный rule-set sing-box.
- [`games/aws-udp.json`](games/aws-udp.json) — тот же набор в читаемом виде.
- [`games/aws-cidrs.txt`](games/aws-cidrs.txt) — объединённые IPv4-подсети.
- [`sources.json`](sources.json) — источник, время снимка и параметры отбора.

Источник: [официальный список AWS](https://ip-ranges.amazonaws.com/ip-ranges.json), дата текущего снимка и число подсетей указаны в `sources.json`. Выбраны сервисы `EC2` и `GLOBALACCELERATOR`; пересекающиеся IPv4-сети объединены. IPv6 в этот набор не входит.

## Подключение в Tachyon

В Conditions игровой секции добавьте Rule set:

```text
https://raw.githubusercontent.com/kosttiik/tachyon-rules/main/games/aws-udp.srs
```

**Включите Include rule set IP ranges.** В UCI это `list rule_set_with_subnets`, а не обычный `list rule_set`.

Внутри одного правила одновременно действуют все три условия:

```text
UDP AND destination port 1024-65535 AND destination IP in AWS prefixes
```

Оставьте отдельные поля Domains, IPs и Ports этой игровой UDP-секции пустыми: условия уже заданы внутри SRS. Не добавляйте этот же список в IPs отдельным условием, иначе можно расширить перехват на TCP. Правило Direct_Steam, если используется, должно стоять выше игровой секции.

Список не включает стратегию DPI-обхода и сам по себе ничего не разблокирует. Для секции требуется отдельно подобранная стратегия zapret2. Успешная проверка HTTPS игрового API не доказывает работу матчей и голосовой связи. Диапазоны облака автоматически обновляются описанным ниже workflow.

Пересборка после изменения JSON:

```sh
sing-box rule-set compile games/aws-udp.json -o games/aws-udp.srs
```

Правила используют headless rule-set format v3. В бинарном и читаемом файлах сохраняются ограничения по UDP и портам.

## Автоматическое обновление

[Workflow Update AWS game rules](https://github.com/kosttiik/tachyon-rules/actions/workflows/update-aws-rules.yml) проверяет официальный источник AWS ежедневно в **04:23 UTC / 07:23 МСК**. Его также можно запустить через **Actions → Update AWS game rules → Run workflow**. Изменения скрипта, тестов или workflow запускают проверку автоматически.

Если выбранные IPv4-подсети EC2/GLOBALACCELERATOR изменились, workflow пересобирает JSON, TXT и SRS, обновляет `sources.json` и `SHA256SUMS`, затем коммитит их в `main`. Если менялись только посторонние сервисы AWS или метаданные снимка, коммита нет. Дата в `sources.json` относится к последнему изменению выбранного набора, а не к последней проверке.

Используются актуальный стабильный Python (`3.x`) и последний стабильный релиз sing-box с проверкой SHA256 архива из GitHub Releases. Actions закреплены по SHA: checkout 7.0.1, setup-python 7.1.0. Перед публикацией выполняются тесты отбора подсетей, обратная декомпиляция SRS и проверка сохранности условий **UDP AND 1024–65535 AND IP**. Пустой/некорректный ответ источника или ошибка сборки останавливают обновление, оставляя опубликованные файлы прежними.

URL SRS для Tachyon остаётся тем же. Роутер получит новые данные при своём очередном обновлении списков; workflow не подключается к роутеру и не меняет его настройки. GitHub может задерживать запуск по расписанию и отключает расписания публичных репозиториев после 60 дней отсутствия активности.

Локальная проверка и обновление (Python и `sing-box` должны быть установлены):

```sh
python -m unittest discover -s tests -v
python scripts/update_rules.py
```
