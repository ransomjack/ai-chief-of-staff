# Setup, step by step

Everything happens in a browser: Meta's developer site, GitHub, and Azure Cloud Shell. Nothing is
installed on a laptop. Put secrets only into Key Vault, never into chats, issues or repo files.

Time: about an hour the first time.

## 1. Meta app and WhatsApp (about 20 minutes)

1. Go to **developers.facebook.com** and log in with Facebook. Choose **My Apps > Create app**, use
   case **Connect with customers through WhatsApp** (type Business). Name it "Chief of Staff".
2. Under **WhatsApp > API Setup** Meta shows a free **test number**. Note the **Phone number ID** and
   the **WhatsApp Business Account ID**.
3. In **To**, add your own WhatsApp number and confirm the code Meta sends. The test number can only
   message numbers on this list, which is what we want.
4. **App settings > Basic**: copy the **App secret**.
5. **Permanent token** (the token on the API Setup page expires in 24 hours):
   business.facebook.com > Settings > Users > **System users** > Add (role Admin) > **Assign assets**
   (the app, full control) > **Generate token** with `whatsapp_business_messaging` and
   `whatsapp_business_management`, expiry **Never**. Copy it.
6. Make up a long random **verify token** (any text, e.g. 30 random letters). It is used once, in step 6.

## 2. Message templates (5 minutes, approval takes minutes to a day)

**WhatsApp Manager > Message templates > Create template**, category **Utility**, language **English**:

| Name | Body | Button |
|---|---|---|
| `cos_reminder` | `Reminder you scheduled: {{1}}. You set this alert in your Chief of Staff account. Reply DONE to close it or SNOOZE to delay it.` (sample for {{1}}: `Chase Anoop on the year-end deck`) | none |
| `cos_checkin` | `Your daily brief is ready. You turned on this morning summary in your Chief of Staff account. Tap below to see today's meetings, tasks and follow-ups.` | Quick reply: `Show brief` |

If Meta re-categorises one as Marketing it still works; it just costs a little more per message.

## 3. Azure (15 minutes)

1. portal.azure.com > the **>_** icon (Cloud Shell) > **Bash**.
2. Run:
   ```
   git clone https://github.com/ransomjack/ai-chief-of-staff && cd ai-chief-of-staff
   bash scripts/azure_setup.sh
   ```
   (If the repo is ever made private, git asks for a GitHub login; use a token.)
3. Note the printed **Function App name**, **Key Vault name** and **Webhook URL**.

## 4. Secrets into Key Vault

In Cloud Shell (replace `KV` with your vault name; type the values, don't paste them anywhere else):

```
KV=kv-cos-xxxxxx
az keyvault secret set --vault-name $KV -n owner-whatsapp-number --value '91XXXXXXXXXX'
az keyvault secret set --vault-name $KV -n whatsapp-token --value '<permanent token>'
az keyvault secret set --vault-name $KV -n whatsapp-phone-number-id --value '<phone number id>'
az keyvault secret set --vault-name $KV -n whatsapp-app-secret --value '<app secret>'
az keyvault secret set --vault-name $KV -n whatsapp-verify-token --value '<your verify token>'
az keyvault secret set --vault-name $KV -n anthropic-api-key --value '<new Anthropic key>'
```

Use a **new** Anthropic API key just for this project (console.anthropic.com > API keys), so it can be
revoked on its own, and keep your spending limit on.

## 5. Deploy from GitHub (10 minutes, once)

1. In Cloud Shell, create an identity GitHub can sign in as, and trust this repo's `production`
   environment (OIDC, so no password is stored):
   ```
   RG=rg-chief-of-staff; APP=func-cos-xxxxxx
   APPID=$(az ad app create --display-name gh-chief-of-staff --query appId -o tsv)
   az ad sp create --id $APPID -o none
   az role assignment create --assignee $APPID --role "Website Contributor" \
     --scope $(az functionapp show -n $APP -g $RG --query id -o tsv) -o none
   az ad app federated-credential create --id $APPID --parameters '{"name":"gh-production",
     "issuer":"https://token.actions.githubusercontent.com",
     "subject":"repo:ransomjack/ai-chief-of-staff:environment:production",
     "audiences":["api://AzureADTokenExchange"]}'
   echo "AZURE_CLIENT_ID=$APPID"; az account show --query "{AZURE_TENANT_ID:tenantId, AZURE_SUBSCRIPTION_ID:id}"
   ```
2. GitHub repo > Settings > **Environments** > New `production`. Add secrets `AZURE_CLIENT_ID`,
   `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, and a variable `FUNCTION_APP_NAME`.
3. Actions > **deploy** > Run workflow.

## 6. Connect Meta to the webhook

Meta app > **WhatsApp > Configuration > Webhook > Edit**: Callback URL = the Webhook URL from step 3,
Verify token = your verify token. **Verify and save**, then under **Webhook fields** subscribe to
**messages**.

Send "hi" from your phone to the test number. It should answer.

## 7. Optional: GitHub project updates

github.com > Settings > Developer settings > **Fine-grained tokens** > Generate. Repository access:
the repos to watch. Permissions (all **Read-only**): Actions, Contents, Pull requests, Metadata.
Expiry: 90 days (put a reminder in the bot to renew it). Then:

```
az keyvault secret set --vault-name $KV -n github-token --value '<token>'
az functionapp config appsettings set -n $APP -g $RG --settings \
  GITHUB_TOKEN="@Microsoft.KeyVault(VaultName=$KV;SecretName=github-token)"
```

## 8. Optional: personal Outlook calendar and mail

1. portal.azure.com > **Microsoft Entra ID > App registrations > New registration**. Name
   "Chief of Staff Outlook", account type **Personal Microsoft accounts only**. Register.
2. **Authentication** > **Allow public client flows: Yes**. Save.
3. **API permissions** > Add > Microsoft Graph > **Delegated**: `User.Read`, `Calendars.Read`,
   `Mail.Read`, `offline_access`.
4. Copy the **Application (client) ID**. In Cloud Shell:
   ```
   python3 scripts/outlook_login.py <client id>
   ```
   Open the link, sign in with your personal Outlook account, approve. Store the printed token:
   ```
   az keyvault secret set --vault-name $KV -n ms-refresh-token --value '<token>'
   az functionapp config appsettings set -n $APP -g $RG --settings MS_CLIENT_ID=<client id> \
     MS_REFRESH_TOKEN="@Microsoft.KeyVault(VaultName=$KV;SecretName=ms-refresh-token)"
   ```

Microsoft hands out a new refresh token each time it is used; the assistant keeps the newest one in its
own table, so the Key Vault copy is only the starting point.

## 9. Later: a real number

When it works, get a new SIM (one that has never been on WhatsApp), add it under **WhatsApp > API
Setup > Add phone number**, verify it, and update the `whatsapp-phone-number-id` secret.

## Checking it is healthy

- Function App > **Monitoring > Log stream** shows each message and reminder.
- Message the bot "brief": a reply within a few seconds means everything is wired.
- "/reset" clears the conversation memory (tasks and reminders stay).
