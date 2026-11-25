# Отладка: почему «из коробки» не взлетело

Рабочие заметки к ЛР 3 — полный разбор проблем, встреченных при развёртывании
актуального `nextcloud:stable-apache` (34.0.6) с `postgres:14` в k8s.
Краткая версия — в README.

Сначала обе обязательные доработки выглядели рабочими, но установка падала в
цикле `Retrying install...`. Разбор по логам и исходникам установщика:

1. **Симптом**: `kubectl logs` nextcloud —
   `SQLSTATE[42501]: permission denied for table oc_migrations`, в логах
   postgres те же отказы. В БД — таблицы и роли `oc_admin`, `oc_admin2`, …
   хотя никто таких не создавал.

2. **Причина** (по исходникам `lib/private/Setup/PostgreSQL.php`): если
   роль, под которой ставится Nextcloud, имеет права `CREATEROLE`/
   `SUPERUSER`, установщик включает «отделение пользователя БД» — создаёт
   отдельную роль с захардкоженным именем `oc_admin` (+счётчик при
   повторах) и случайным паролем. На postgres:14 этот путь ломается: таблицы
   создаёт одна роль, а читает другая → permission denied → бесконечные
   ретраи с новыми ролями.

3. **Фикс** (`pg_init_configmap.yml`): init-SQL в
   `/docker-entrypoint-initdb.d`, который сразу после initdb снимает с
   `nc_dbuser` суперправа — приложению они и не нужны. Без `CREATEROLE`
   установщик использует `POSTGRES_USER` как есть:

   ```
   $ kubectl exec deploy/postgres -- psql -U nc_dbuser -d nextcloud \
       -c "SELECT rolname, rolsuper, rolcreaterole FROM pg_roles WHERE rolname='nc_dbuser';"
    rolname  | rolsuper | rolcreaterole
   ----------+----------+---------------
    nc_dbuser | f        | f
   ```

4. Второй эффект: ретраи установки оставляют в БД админ-пользователя, и
   повторный запуск говорит «The Login is already being used». Поэтому после
   экспериментов с подами цикл всегда один и тот же: погасить nextcloud →
   пересоздать под postgres (чистый initdb) → запустить nextcloud.

5. Третий, самый поучительный слой: **рестарт контейнера = потеря
   writable-слоя** (в отличие от рестарта пода с volume). Стоило liveness
   один раз убить контейнер (медленный момент на 2-CPU кластере; отдельно
   проявился дефолтный `timeoutSeconds: 1` у проб), как nextcloud терял
   config.php, пытался переустановиться и попадал в CrashLoopBackOff
   «Login already used». Лечение — то же, что и для эксперимента scale 0→1:
   **PVC** (`nextcloud_pvc.yml`, 5Gi на `/var/www/html`; официальный образ
   рассчитан на такую схему — при пустом томе он раскладывает код, при
   установленном — просто стартует). Проверка: удаляем под — новый под Ready
   за 31 c, в логах **0** попыток установки:

   ```
   $ kubectl delete pod -l app=nextcloud
   $ kubectl wait --for=condition=Ready pod -l app=nextcloud --timeout=300s
   $ kubectl logs -l app=nextcloud | grep -c "Starting nextcloud installation"
   0
   ```

6. Пробы: kubelet присылает `Host: <IP пода>`, а Nextcloud отвечает 400 на
   недоверенные домены — в пробы добавлен
   `httpHeaders: [{name: Host, value: localhost}]`; `timeoutSeconds: 5`
   вместо дефолтной 1.

Попутные находки:

- `minikube delete` + свежий кластер понадобился ещё и потому, что в старом
  контейнере ноды остались данные от прошлых прогонов (таблицы чужого
  владельца).
- Dashboard живёт по полному пути
  `http://<port>/api/v1/namespaces/kubernetes-dashboard/services/http:kubernetes-dashboard:/proxy/` —
  голый порт отдаёт JSON discovery apiserver.
- Полная перезагрузка хоста воспроизводит сценарий «question 2» для postgres,
  если у него нет PVC (контейнер пересоздаётся с пустым writable-слоем) —
  поэтому появился `pg_pvc.yml`.
