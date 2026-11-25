# Полные выводы терминала (ход работы)

Каждый шаг в README показывает ключевые строки; здесь — полные логи прогонов.

## 1. Запуск кластера

```
$ minikube start --driver=docker --cpus=2 --memory=4096
...
* Готово! kubectl настроен для использования кластера "minikube"

$ kubectl get nodes
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   31s   v1.37.0
```

(после включения calico для NetworkPolicy кластер пересоздавался с `--cni=calico`)

## 2. Исходные манифесты

```
$ kubectl create -f original/pg_configmap.yml -f original/pg_service.yml -f original/pg_deployment.yml
configmap/postgres-configmap created
service/postgres-service created
deployment.apps/postgres created

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

```
$ kubectl logs -l app=postgres | head
The files belonging to this database system will be owned by user "postgres".
The database cluster will be initialized with locale "en_US.utf8".
The default database encoding has accordingly been set to "UTF8".
fixing permissions on existing directory /var/lib/postgresql/data ... ok
```

```
$ kubectl create -f original/nextcloud.yml
secret/nextcloud-secret created
deployment.apps/nextcloud created

$ kubectl logs -l app=nextcloud
Initializing nextcloud 34.0.6.2 ...
```

Секрет не раскрывается:

```
$ kubectl get secret nextcloud-secret
NAME               TYPE     DATA   AGE
nextcloud-secret   Opaque   1      97s

$ kubectl describe secret nextcloud-secret | tail -3
Data
====
NEXTCLOUD_ADMIN_PASSWORD:  11 bytes
```

## 3. Демо порядка манифестов

```
$ kubectl create -f nextcloud_deployment.yml   # первым!
$ kubectl get pods
NAME                        READY   STATUS                       RESTARTS   AGE
nextcloud-b7d9d8fdc-c6xq7   0/1     CreateContainerConfigError   0          8s

$ kubectl describe pod -l app=nextcloud | tail -3
Warning  Failed   7s (x2 over 8s)  kubelet  Error: configmap "nextcloud-configmap" not found

# ...применяем остальные манифесты, под оживает сам:
$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
nextcloud-b7d9d8fdc-c6xq7   0/1     Running   0          24s
postgres-848ffcb678-nd8dh   1/1     Running   0          10s
```

## 4. Доработанная конфигурация

```
Starting nextcloud installation
Nextcloud was successfully installed
Setting trusted domains…
Initializing finished
[...] Apache/2.4.71 (Debian) PHP/8.5.13 configured -- resuming normal operations
```

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

(в hardened-версии postgres-service стал ClusterIP, добавлены PVC и NetworkPolicy)

```
$ kubectl get secret postgres-secret -o jsonpath='{.data.POSTGRES_USER}{"\n"}{.data.POSTGRES_PASSWORD}{"\n"}'
bmNfZGJ1c2Vy
UGdMYWIzLTIwMjY=

$ kubectl get secret postgres-secret -o jsonpath='{.data.POSTGRES_USER}' | base64 -d
nc_dbuser
$ kubectl get secret postgres-secret -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
PgLab3-2026
```

## 5. Доступ снаружи

```
$ kubectl expose deployment nextcloud --type=NodePort --port=80
service/nextcloud exposed

$ kubectl get svc nextcloud
NAME        TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
nextcloud   NodePort   10.110.2.179   <none>        80:30679/TCP   3s

$ minikube service nextcloud --url
http://127.0.0.1:65506

$ curl -s http://127.0.0.1:65506/status.php
{"installed":true,"maintenance":false,"needsDbUpgrade":false,
 "version":"34.0.6.2","versionstring":"34.0.6","edition":"",
 "productname":"Nextcloud","extendedSupport":false}
```

Порты туннелей ephemeral — при повторном прогоне будут другие.

## 7. Эксперимент scale 0 → 1 (полный)

```
$ kubectl scale deployment postgres --replicas=0
deployment.apps/postgres scaled
$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
nextcloud-94d7d599-c8x4t    1/1     Running   0          6m46s

$ kubectl scale deployment postgres --replicas=1
deployment.apps/postgres scaled

$ kubectl exec deploy/postgres -- psql -U nc_dbuser -d nextcloud \
    -c "SELECT count(*) AS tables FROM pg_tables WHERE schemaname='public';"
 tables
--------
      0
(1 row)

$ kubectl describe pod -l app=nextcloud | tail -3
Warning  Unhealthy  32s (x2 over 42s)  kubelet  Readiness probe failed: Get "http://10.244.0.21:80/status.php": context deadline exceeded
Warning  Unhealthy  13s (x2 over 43s)  kubelet  Liveness probe failed: HTTP probe failed with statuscode: 500
Warning  Unhealthy  3s (x5 over 53s)   kubelet  Readiness probe failed: HTTP probe failed with statuscode: 500

$ kubectl get pods
NAME                        READY   STATUS    RESTARTS   AGE
nextcloud-94d7d599-c8x4t    0/1     Running   0          7m37s
```

Примечание: эксперимент проводился до добавления `pg_pvc.yml` (без PVC у
postgres) — именно так и воспроизводится «пустая база». С PVC данные бы
пережили (как у greetings и nextcloud).
