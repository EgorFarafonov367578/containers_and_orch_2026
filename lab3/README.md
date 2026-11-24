# ЛР 3. Kubernetes (minikube): Nextcloud + PostgreSQL

Задача — развернуть в локальном minikube связку Nextcloud + PostgreSQL из
YAML-манифестов, а затем доработать пример из методички:

1. **postgres**: `POSTGRES_USER` и `POSTGRES_PASSWORD` перенесены из ConfigMap
   в **Secret** (новый манифест `pg_secret.yml`);
2. **nextcloud**: «плоские» переменные (`NEXTCLOUD_UPDATE`,
   `ALLOW_EMPTY_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DB`,
   `NEXTCLOUD_TRUSTED_DOMAINS`, `NEXTCLOUD_ADMIN_USER`) перенесены из
   Deployment в **ConfigMap** (новый манифест `nextcloud_configmap.yml`);
3. **nextcloud**: добавлены **readiness- и liveness-пробы** (`httpGet
   /status.php`).

Кроме обязательных пунктов пришлось добавить два «боевых» фикса, без которых
свежий `nextcloud:stable-apache` (34.0.6) с `postgres:14` в k8s не
разворачивается — подробности в разделе «Отладка».

Окружение: macOS (arm64), Docker Desktop, minikube v1.39.0 (драйвер docker),
kubectl v1.37.2, Kubernetes v1.37.0.

## Что где лежит

```
lab3/
  original/                    # манифесты из методички — «как было»
    pg_configmap.yml           #   DB + USER + PASSWORD в ConfigMap
    pg_service.yml
    pg_deployment.yml
    nextcloud.yml              #   Secret (пароль админа) + Deployment, без проб
  pg_configmap.yml             # «как стало»: только POSTGRES_DB
  pg_secret.yml                # NEW: postgres-secret (USER, PASSWORD)
  pg_service.yml               # без изменений (NodePort 5432)
  pg_deployment.yml            # envFrom: configMapRef + secretRef + init-SQL
  pg_init_configmap.yml        # NEW: init-SQL для postgres (см. «Отладка»)
  nextcloud_configmap.yml      # NEW: плоские переменные nextcloud
  nextcloud_secret.yml         # NEXTCLOUD_ADMIN_PASSWORD
  nextcloud_deployment.yml     # envFrom + liveness/readiness пробы
  screenshots/                 # скриншоты UI (логин, файлы, dashboard)
  README.md                    # этот отчёт
```

Пароли в манифестах — учебные, придуманы для этой работы (`PgLab3-2026`,
`NcLab3-2026`); репозиторий учебный, в реальном окружении секреты так в git
не кладут.

## Ход работы

### 1. Запуск кластера

```bash
minikube start --driver=docker --cpus=2 --memory=4096
kubectl get nodes
docker ps   # контейнер minikube
```

```
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   31s   v1.37.0
```

### 2. Исходные манифесты (как в методичке)

```bash
kubectl create -f original/pg_configmap.yml -f original/pg_service.yml -f original/pg_deployment.yml
```

```
configmap/postgres-configmap created
service/postgres-service created
deployment.apps/postgres created
```

```
$ kubectl get all,cm
NAME                            READY   STATUS              RESTARTS   AGE
pod/postgres-54d5c5bf9b-b64s5   0/1     ContainerCreating   0          0s

NAME                       TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
service/kubernetes         ClusterIP   10.96.0.1       <none>        443/TCP          31s
service/postgres-service   NodePort    10.109.63.74    <none>        5432:30545/TCP   0s

NAME                                  DESIRED   CURRENT   READY   AGE
replicaset.apps/postgres-54d5c5bf9b   1         1        0       0s

NAME                           DATA   AGE
configmap/postgres-configmap   3     0s
```

Журналы пода postgres (`kubectl logs`) — чистая инициализация кластера БД:

```
The database cluster will be initialized with locale "en_US.utf8".
The default database encoding has accordingly been set to "UTF8".
fixing permissions on existing directory /var/lib/postgresql/data ... ok
```

Nextcloud — второй документ манифеста `original/nextcloud.yml` (Secret +
Deployment), под стартует и запускает самоинициализацию:

```bash
kubectl create -f original/nextcloud.yml
kubectl logs -l app=nextcloud
```

```
secret/nextcloud-secret created
deployment.apps/nextcloud created
...
Initializing nextcloud 34.0.6.2 ...
```

Секрет при просмотре содержимого не раскрывает — видно только количество
ключей и размер в байтах:

```
$ kubectl get secret nextcloud-secret
NAME               TYPE     DATA   AGE
nextcloud-secret   Opaque   1      97s

$ kubectl describe secret nextcloud-secret | tail -3
Data
====
NEXTCLOUD_ADMIN_PASSWORD:  11 bytes
```

### 3. Порядок манифестов (демо к вопросу 1)

Убираем исходные объекты и применяем доработанные — нарочно начиная с
деплоймента nextcloud, пока его ConfigMap/Secret не созданы:

```bash
kubectl delete deployment postgres nextcloud
kubectl delete service postgres-service
kubectl delete cm postgres-configmap
kubectl delete secret nextcloud-secret

kubectl create -f nextcloud_deployment.yml   # первым!
kubectl get pods
```

```
NAME                        READY   STATUS                       RESTARTS   AGE
nextcloud-b7d9d8fdc-c6xq7   0/1     CreateContainerConfigError   0          8s
```

```
$ kubectl describe pod -l app=nextcloud | tail -3
Warning  Failed   7s (x2 over 8s)  kubelet  Error: configmap "nextcloud-configmap" not found
```

Создаём остальные объекты — и тот же под оживает без пересоздания:

```bash
kubectl create -f pg_configmap.yml -f pg_secret.yml -f pg_service.yml \
  -f pg_deployment.yml -f nextcloud_configmap.yml -f nextcloud_secret.yml
```

```
NAME                        READY   STATUS    RESTARTS   AGE
nextcloud-b7d9d8fdc-c6xq7   0/1     Running   0          24s
postgres-848ffcb678-nd8dh   1/1     Running   0          10s
```

### 4. Доработанная конфигурация: установка и пробы

После «химии» из раздела «Отладка» установка проходит до конца:

```
Starting nextcloud installation
Nextcloud was successfully installed
Setting trusted domains…
Initializing finished
[...] Apache/2.4.71 (Debian) PHP/8.5.13 configured -- resuming normal operations
```

Пробы в `describe` (обратите внимание: имя порта `http`, а не цифра):

```
$ kubectl describe pod -l app=nextcloud
    Liveness:   http-get http://:http/status.php delay=120s timeout=5s period=30s successThreshold=1 failureThreshold=5
    Readiness:  http-get http://:http/status.php delay=30s timeout=5s period=10s successThreshold=1 failureThreshold=3
    Environment Variables from:
      nextcloud-configmap  ConfigMap  Optional: false
      postgres-secret      Secret     Optional: false
    Environment:
      NEXTCLOUD_ADMIN_PASSWORD:  <set to the key 'NEXTCLOUD_ADMIN_PASSWORD' in secret 'nextcloud-secret'>  Optional: false
```

Итоговое состояние кластера:

```
$ kubectl get all,cm,secret
NAME                            READY   STATUS    RESTARTS   AGE
pod/nextcloud-94d7d599-c8x4t    1/1     Running   0          39s
pod/postgres-75b8c699bf-xt4zq   1/1     Running   0          50s

NAME                       TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
service/postgres-service   NodePort    10.106.208.44   <none>        5432:30623/TCP   36m

NAME                       READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/nextcloud   1/1     1            1           39s
deployment.apps/postgres    1/1     1            1           36m

NAME                            DATA   AGE
configmap/nextcloud-configmap   6     62m
configmap/postgres-configmap    1     62m
configmap/postgres-initdb       1     36m

NAME                      TYPE     DATA   AGE
secret/nextcloud-secret   Opaque   1      62m
secret/postgres-secret    Opaque   2      62m
```

Секреты хранятся в base64 и декодируются ровно в значения манифеста:

```
$ kubectl get secret postgres-secret -o jsonpath='{.data.POSTGRES_USER}{"\n"}{.data.POSTGRES_PASSWORD}{"\n"}'
bmNfZGJ1c2Vy
UGdMYWIzLTIwMjY=

$ kubectl get secret postgres-secret -o jsonpath='{.data.POSTGRES_USER}' | base64 -d
nc_dbuser
$ kubectl get secret postgres-secret -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
PgLab3-2026
```

### 5. Доступ снаружи (NodePort)

```bash
kubectl expose deployment nextcloud --type=NodePort --port=80
minikube service nextcloud --url
```

```
service/nextcloud exposed
NAME        TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
nextcloud   NodePort   10.110.2.179   <none>        80:30679/TCP   3s
http://127.0.0.1:65506
```

```
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:65506/status.php
200

$ curl -s http://127.0.0.1:65506/status.php
{"installed":true,"maintenance":false,"needsDbUpgrade":false,
 "version":"34.0.6.2","versionstring":"34.0.6","edition":"",
 "productname":"Nextcloud","extendedSupport":false}
```

Вход в UI: логин `ncadmin`, пароль из `nextcloud_secret.yml` — скриншоты в
`screenshots/`.

### 6. Dashboard

```bash
minikube dashboard --url
# http://127.0.0.1:49678
```

### 7. Эксперимент: scale postgres 0 → 1

```
$ kubectl scale deployment postgres --replicas=0
deployment.apps/postgres scaled
$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
nextcloud-94d7d599-c8x4t    1/1     Running   0          6m46s
```

Pod postgres удалён вместе с writable-слоем (PVC у нас нет). Возвращаем:

```
$ kubectl scale deployment postgres --replicas=1
deployment.apps/postgres scaled
```

Новый под делает чистый initdb — база пустая:

```
$ kubectl exec deploy/postgres -- psql -U nc_dbuser -d nextcloud \
    -c "SELECT count(*) AS tables FROM pg_tables WHERE schemaname='public';"
 tables
--------
      0
(1 row)
```

Конфигурация nextcloud при этом уцелела (она в его собственном поде), но
приложение «видит» пропавшие таблицы — readiness-проба `/status.php`
перестаёт отвечать 200, и kubelet помечает под нездоровым:

```
$ kubectl describe pod -l app=nextcloud | tail -3
Warning  Unhealthy  32s (x2 over 42s)  kubelet  Readiness probe failed: Get "http://10.244.0.21:80/status.php": context deadline exceeded
Warning  Unhealthy  13s (x2 over 43s)  kubelet  Liveness probe failed: HTTP probe failed with statuscode: 500
Warning  Unhealthy  3s (x5 over 53s)   kubelet  Readiness probe failed: HTTP probe failed with statuscode: 500

$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
nextcloud-94d7d599-c8x4t    0/1     Running   0          7m37s
```

To есть nextcloud живой, но «не готов» — сервис бы не пускал на него
трафик; liveness через порог неудач перезапустит контейнер, что не поможет:
таблиц в БД больше нет. Лечится только переустановкой (или PVC — см. ответ
на вопрос 2).

## Что изменено и почему

**Secret вместо ConfigMap для кредов postgres.** ConfigMap — открытое
хранилище настроек: любой с доступом к API видит значения, они попадают в env
в открытом виде и часто утекают в логи и экспорты. `POSTGRES_USER` /
`POSTGRES_PASSWORD` — учётные данные, им место в Secret (base64 + отдельные
механизмы RBAC, возможность шифрования etcd). В ConfigMap осталась только
нечувствительная настройка `POSTGRES_DB`.

**ConfigMap для переменных nextcloud.** `NEXTCLOUD_UPDATE`,
`ALLOW_EMPTY_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DB`,
`NEXTCLOUD_TRUSTED_DOMAINS`, `NEXTCLOUD_ADMIN_USER` — это конфигурация, а не
секреты. Вынос в ConfigMap убирает их из Deployment (манифест становится
переиспользуемым между окружениями), а смена настройки не требует правки
деплоймента. Исключение — `NEXTCLOUD_ADMIN_PASSWORD`, она осталась в Secret.
Креды postgres nextcloud получает через `envFrom: secretRef:
postgres-secret` — один источник правды на оба контейнера.

**Пробы.**

- `readinessProbe` (initialDelay 30 s, period 10 s) — пока `/status.php` не
  отвечает 200, под не получает трафик: установка Nextcloud занимает десятки
  секунд, без пробы Service сразу отправил бы пользователей на не поднятое
  приложение. Работу видно и «в минусе»: в эксперименте scale 0→1 именно
  readiness первым сообщил о сломанной БД.
- `livenessProbe` (initialDelay 120 s, period 30 s, timeout 5 s,
  failureThreshold 5) — если контейнер завис, кубер перезапустит его; пороги
  мягкие, чтобы не убивать под при медленной установке. Дефолтный
  `timeoutSeconds: 1` оказался опасен: одно медленное мгновение PHP — и
  пять «неудач» подряд убивали контейнер, который без PVC потом не мог
  переустановиться (см. «Отладка», п. 4).
- Путь `/status.php` лёгкий и есть в официальном образе; порт указан по имени
  `http` — при смене порта контейнера проба не сломается. Значения порогов —
  как в официальном Helm-чарте Nextcloud.
- Nuanс реализации: kubelet присылает `Host: <IP пода>`, а Nextcloud отвечает
  400 на недоверенные домены, поэтому в пробы добавлен
  `httpHeaders: [{name: Host, value: localhost}]` — `localhost` уже есть в
  `NEXTCLOUD_TRUSTED_DOMAINS`.

## Отладка: почему «из коробки» не взлетело

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

Попутная находка: `minikube delete` + свежий кластер понадобился ещё и
потому, что в старом контейнере ноды остались данные от прошлых прогонов
(таблицы чужого владельца) — состояние пода не всегда «столько, сколько
живёт под», если нода пережила несколько прогонов.

## Ответы на вопросы

**1. Важен ли порядок применения манифестов?**

Нет, объекты в кластере создаются независимо и не «знают» друг о друге —
kubectl create для каждого файла самодостаточен. Но есть практический
нюанс: если Deployment применяется раньше ConfigMap/Secret, на которые
ссылается его `envFrom`, kubelet не может собрать контейнер, и под висит в
`CreateContainerConfigError`, пока недостающий объект не появится (что мы и
показали в разделе 3: применили деплоймент первым — под тут же «ожил» после
создания конфигмапы, без пересоздания). То есть порядок влияет на момент
готовности, но не на результат.

**2. Что (и почему) произойдёт, если отскейлить postgres в 0, затем в 1, и
зайти в Nextcloud?**

При `--replicas=0` Deployment удаляет под вместе с его writable-слоем —
PersistentVolume в манифестах нет, данные БД живут ровно столько, сколько
живёт под. При `--replicas=1` создаётся новый под, официальный образ postgres
видит пустую директорию и инициализирует **пустую** базу с теми же кредами из
Secret. Конфигурация Nextcloud уцелела (config.php в его собственном поде), поэтому он спокойно подключается, но не находит своих таблиц: приложение
отвечает ошибкой, readiness-проба уходит из 200 (у нас — таймауты и 500), под
становится 0/1, liveness со временем перезапустит контейнер — что не поможет.
Практический вывод: базам данным в k8s нужен PVC (persistent volume claim),
переживающий пересоздание пода; эксперимент из раздела 7 — ровно эта
ситуация, зафиксированная выводами команд.

## Проверка

| Проверка | Результат |
|---|---|
| `kubectl get all,cm,secret` | всё Running/Ready, объекты на месте |
| `kubectl describe pod nextcloud-*` | видны readiness/liveness пробы и envFrom |
| `kubectl get secret -o yaml` + `base64 -d` | значения совпадают с манифестом |
| `curl /status.php` | HTTP 200, `installed:true` |
| Логин `ncadmin` + пароль из Secret | вход в UI успешен (screenshots/) |
| scale postgres 0 → 1 | база пустая (0 таблиц), пробы 500/timeout, под 0/1 |
| Порядок манифестов | деплоймент первым → `CreateContainerConfigError`, оживает после создания ConfigMap |
