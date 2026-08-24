# ClouDO Helm Chart

Helm chart per distribuire ClouDO su Kubernetes.

## Componenti

- `orchestrator`: API backend esposta su porta `80`
- `ui`: frontend esposto su porta `3000`
- `worker-*`: worker per le queue configurate in `values.yaml`
- `bootstrap`: Job Helm hook che crea tabelle, queue, blob container e utente admin
- `azurite`: emulator Azure Storage opzionale per dev/test

## Installazione

```bash
helm upgrade --install cloudo ./deploy/helm/cloudo \
  --namespace cloudo \
  --create-namespace
```

Per un controllo preliminare:

```bash
helm lint ./deploy/helm/cloudo
helm template cloudo ./deploy/helm/cloudo
```

## Values

File principali:

- `values.yaml`: configurazione base
- `values-dev.yaml`: profilo dev con Azurite
- `values-azure-example.yaml`: esempio prod con Azure Storage e Workload Identity

### Dev

```bash
helm upgrade --install cloudo ./deploy/helm/cloudo \
  -n cloudo-dev --create-namespace \
  -f deploy/helm/cloudo/values-dev.yaml
```

Questo profilo abilita:

- namespace `cloudo-dev`
- Azurite in cluster
- ingress disabilitato
- secret di sviluppo inline

### Production

```bash
helm upgrade --install cloudo ./deploy/helm/cloudo \
  -n cloudo --create-namespace \
  -f deploy/helm/cloudo/values-azure-example.yaml \
  --set secrets.azureWebJobsStorage="<connection-string>" \
  --set secrets.cloudoSecretKey="<secret>" \
  --set secrets.sessionSecret="<secret>"
```

In produzione:

- `azurite.enabled=false`
- usa Azure Storage reale o `existingSecretName`
- abilita l'ingress con host e TLS corretti

## Parametri principali

| Chiave                         | Descrizione                                     |
| ------------------------------ | ----------------------------------------------- |
| `global.namespace`             | Namespace target del rilascio                   |
| `image.registry` / `image.tag` | Immagini dei container                          |
| `serviceAccount.create`        | Crea un ServiceAccount dedicato                 |
| `existingSecretName`           | Usa un Secret esistente invece di crearne uno   |
| `secrets.*`                    | Credenziali e chiavi applicative                |
| `config.*`                     | Configurazione runtime condivisa                |
| `orchestrator.*`               | Replica, risorse e scheduling dell'orchestrator |
| `workers[]`                    | Definizione dei worker e delle relative HPA     |
| `ui.*`                         | Replica, URL e risorse del frontend             |
| `ingress.*`                    | Host, TLS e annotazioni Ingress                 |
| `bootstrap.*`                  | Abilita il job iniziale e l'admin user          |
| `azurite.*`                    | Emulator Azure Storage e persistence            |

## Secret attesi

Se il chart gestisce i secret, crea `cloudo-secrets` con queste chiavi:

- `AzureWebJobsStorage`
- `CLOUDO_SECRET_KEY`
- `SESSION_SECRET`
- `APPROVAL_SECRET`
- `SLACK_TOKEN_DEFAULT`
- `SLACK_CHANNEL_DEFAULT`
- `JSM_API_KEY_DEFAULT`
- `GITHUB_TOKEN`
- `GOOGLE_CLIENT_ID`
- `FUNCTION_KEY`

## Accesso

Con ingress attivo:

- UI: `http(s)://<host>/`
- API health: `http(s)://<host>/api/healthz`

Con ingress disabilitato:

```bash
kubectl -n <namespace> port-forward svc/cloudo-ui 3000:3000
kubectl -n <namespace> port-forward svc/orchestrator 8080:80
```

## Note sul bootstrap

Il job `cloudo-storage-bootstrap` gira come hook `post-install` e `post-upgrade`.
Se lo disabiliti, devi creare prima le risorse Azure e l'admin user.

## Workload Identity

Per usare una Managed Identity su AKS, annota il ServiceAccount:

```yaml
serviceAccount:
  annotations:
    azure.workload.identity/client-id: "<managed-identity-client-id>"
```
