# Игровые правила для Tachyon

Набор адресов AWS EC2 и Global Accelerator всех регионов для проверки игрового UDP-трафика. Это список облачных подсетей, а не точный перечень игровых серверов: он включает также неигровые сервисы AWS.

## Файлы

- [`games/aws-udp.srs`](games/aws-udp.srs) — готовый бинарный rule-set sing-box.
- [`games/aws-udp.json`](games/aws-udp.json) — тот же набор в читаемом виде.
- [`games/aws-cidrs.txt`](games/aws-cidrs.txt) — 752 объединённые IPv4-подсети.
- [`sources.json`](sources.json) — источник, время снимка и параметры отбора.

Источник: [официальный список AWS](https://ip-ranges.amazonaws.com/ip-ranges.json), снимок **22 октября 2026, 06:57:05 UTC**. Выбраны сервисы `EC2` и `GLOBALACCELERATOR`; пересекающиеся IPv4-сети объединены. IPv6 в этот набор не входит.

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

Список не включает стратегию DPI-обхода и сам по себе ничего не разблокирует. Для секции требуется отдельно подобранная стратегия zapret2. Успешная проверка HTTPS игрового API не доказывает работу матчей и голосовой связи. Это фиксированный снимок; диапазоны облака со временем меняются.

Пересборка после изменения JSON:

```sh
sing-box rule-set compile games/aws-udp.json -o games/aws-udp.srs
```

Правила используют headless rule-set format v3. В бинарном и читаемом файлах сохраняются ограничения по UDP и портам.
