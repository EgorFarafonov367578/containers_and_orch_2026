# ИБ-аудит архитектуры и hardening

Полная версия к разделу README «ИБ-аудит и hardening». Модель угроз —
требование «взлом одного сервиса не даёт доступ ко всем».

## Что проверяли и что нашли

| # | Находка | Критичность | Статус |
|---|---|---|---|
| 1 | Секреты postgres открыто лежат в `config.php` nextcloud (`dbuser`/`dbpassword`) и в env пода — так устроен сам Nextcloud, убрать нельзя | присущая | компенсировано (см. 5) |
| 2 | `postgres-service` — NodePort: БД экспонирована на порт ноды | высокая | исправлено → ClusterIP |
| 3 | Ни одной NetworkPolicy: любой под мог стучаться к `postgres:5432` | высокая | исправлено → default-deny + allow nextcloud only |
| 4 | Секреты в git открытым текстом (`stringData`) | средняя | принято осознанно (учебный репо; в проде — SOPS/Sealed Secrets/External Secrets) |
| 5 | `nc_dbuser` после initdb — суперюзер и владелец maintenance-БД `postgres`/`template1` | средняя | исправлено → init-SQL: `db_owner`, демоушн, REVOKE |
| 6 | PG14 даёт PUBLIC CREATE в схеме public любой базы | средняя | исправлено → REVOKE (PG15 делает сам) |
| 7 | Поды от root, примонтирован SA-токен, сервис-линки в env | средняя | исправлено (частично: root внутри nc/pg — свойство образов) |
| 8 | `enableServiceLinks` раздаёт env о всех сервисах каждому поду | низкая | исправлено |

## Изоляция секретов (главное требование)

| Под | Секреты в env | Вывод при взломе |
|---|---|---|
| greetings | **0** (только свой ConfigMap без паролей) | утечек нет |
| nextcloud | postgres-secret + свой nextcloud-secret | креды ограниченной БД-роли |
| postgres | только postgres-secret | по назначению |

Украденный пароль nc_dbuser даёт: контроль только над БД `nextcloud`;
`rolsuper=f, rolcreatedb=f, rolcreaterole=f, rolreplication=f`; CREATE в
maintenance-БД отозван (`has_database_privilege(...,'postgres','CREATE') = f`).

## Живые проверки после hardening

```
=== T1: greetings → postgres:5432 (должен блок) ===
OK заблокировано: TimeoutError          # NetworkPolicy работает (calico)

=== T2: nextcloud → postgres (разрешён) ===
status.php 200                          # легитимный путь жив

=== T3: maintenance-БД ===
has_database_privilege('nc_dbuser','postgres','CREATE') = f

=== T4: SA-токен ===
nextcloud: нет токена; greetings: нет токена

=== T5: greetings — права ===
uid=10001(app) CapEff=0; touch / → Read-only file system

=== T6: внешний доступ ===
nextcloud(туннель) 200; greetings(туннель) 200
```

## Осознанные остаточные риски

- root внутри контейнеров nextcloud/postgres (образы биндят 80 / su-exec
  вниз) — смягчено `allowPrivilegeEscalation: false` + seccomp
  `RuntimeDefault`;
- секреты в git — учебный компромисс (см. #4);
- config.php с кредами на PVC nextcloud — неизбежно для Nextcloud; окно
  закрыто минимальными привилегиями роли.
