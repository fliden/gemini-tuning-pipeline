# Gemini Tuning Pipeline (Vertex AI MLOps)

A lightweight MLOps pipeline to automate **Supervised Fine-Tuning (SFT)** of **Gemini** models on Google Cloud Vertex AI.

This repository uses **GitHub Actions**, **Workload Identity Federation**, and the **Vertex AI API** to provide a secure, "fire-and-forget" training workflow without managing long-lived service account keys.

## 🚀 Features

* **Secure Authentication:** Uses OpenID Connect (OIDC) with Workload Identity Federation (no JSON keys stored in GitHub).
* **Automated Data Management:** Uploads training data to a versioned, timestamped path in Google Cloud Storage.
* **API-First Tuning:** Submits jobs directly to the Vertex AI REST API via `curl`, bypassing CLI lag for new model features.
* **Cost Effective:** Defaults to `gemini-2.0-flash-001` for rapid, low-cost experimentation.

## 📂 Repository Structure

```text
.
├── .github/
│   └── workflows/
│       └── tune-model.yml    # Main CI/CD pipeline definition
├── data/
│   └── training.jsonl        # Default training dataset
├── scripts/
│   └── validate_jsonl.sh     # Helper to verify JSONL format before pushing
└── README.md
```

## 🛠️ Prerequisites

1.  **Google Cloud Project** with billing enabled.
2.  **Vertex AI API** enabled (`aiplatform.googleapis.com`).
3.  **Cloud Storage Bucket** created in `us-central1`.

## ⚙️ One-Time Setup

### 1. Google Cloud Configuration (CLI)

Run these commands locally to set up the Service Account and Workload Identity Federation (WIF). This uses the "Master Key" strategy to authorize **all repositories** owned by your GitHub user to use this pipeline.

```bash
# --- Variables (Update these) ---
PROJECT_ID="your-project-id"
SA_NAME="github-trainer"
POOL_NAME="github-pool"
GITHUB_USER="your-github-username" # Use your Org name or User name

# 1. Create Service Account
gcloud iam service-accounts create $SA_NAME --display-name="GitHub Actions Trainer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 2. Grant Permissions
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_EMAIL" --role="roles/storage.objectAdmin"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_EMAIL" --role="roles/aiplatform.user"

# 3. Create Workload Identity Pool & Provider
gcloud iam workload-identity-pools create $POOL_NAME --location="global" --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool=$POOL_NAME \
  --issuer-uri="[https://token.actions.githubusercontent.com](https://token.actions.githubusercontent.com)" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == '${GITHUB_USER}'"

# 4. Bind GitHub User to Service Account (Master Key)
# Get Pool ID
POOL_ID=$(gcloud iam workload-identity-pools describe $POOL_NAME --location="global" --format="value(name)")

# Allow all repos owned by your user to use this service account
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://[iam.googleapis.com/$](https://iam.googleapis.com/$){POOL_ID}/attribute.repository_owner/${GITHUB_USER}"
```

### 2. GitHub Secrets

Add the following secrets to your repository (**Settings** -> **Secrets and variables** -> **Actions**):

| Secret Name | Value Description |
| :--- | :--- |
| `GCP_PROJECT_ID` | Your Google Cloud Project ID. |
| `GCP_SERVICE_ACCOUNT` | The email address of the service account created above. |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | The full resource name of the provider (e.g., `projects/123.../providers/github-provider`). |
| `GCP_TRAINING_BUCKET_NAME` | The name of your bucket (e.g., `vertex-ai-training-your-project`). |

---

## 🏃 Usage

### 1. Prepare Your Data
Update `data/training.jsonl`.

**Example Format:**
```json
{"systemInstruction": {"role": "system", "parts": [{"text": "You are a code auditor."}]}, "contents": [{"role": "user", "parts": [{"text": "print('hello')"}]}, {"role": "model", "parts": [{"text": "{\"review\": \"Passed\"}"}]}]}
```

### 2. Trigger Training
1.  Go to the **Actions** tab in GitHub.
2.  Select **"Fine-Tune Gemini (CLI MLOps)"**.
3.  Click **Run workflow**.

### 3. Monitor
* **GitHub:** The workflow will finish in ~30 seconds (Fire-and-forget). It will print the **Job ID**.
* **Vertex AI Console:** Go to **Vertex AI** -> **Model Tuning** to watch the job progress.

---

## 🧪 Testing Your Model

Once the job succeeds, use `curl` to test the endpoint. You can find the `ENDPOINT_ID` in the Vertex AI Console details page for your tuned model.

```bash
ENDPOINT_ID="YOUR_ENDPOINT_ID" 
PROJECT_ID="your-project-id"
LOCATION="us-central1"

curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://${LOCATION}[-aiplatform.googleapis.com/v1/projects/$](https://-aiplatform.googleapis.com/v1/projects/$){PROJECT_ID}/locations/${LOCATION}/endpoints/${ENDPOINT_ID}:generateContent" \
  -d '{
    "contents": [{"role": "user", "parts": [{"text": "def MyFunction(): return True"}]}]
  }'
```

## ⚠️ Troubleshooting

| Error | Cause | Fix |
| :--- | :--- | :--- |
| `403 PERMISSION_DENIED` | API not enabled. | Run `gcloud services enable aiplatform.googleapis.com` |
| `Job State Failed` | Bad JSONL format. | Ensure no trailing commas and valid JSON on every line. |
| `Error parsing [service_account]` | Missing variable. | Ensure `GCP_SERVICE_ACCOUNT` secret is set correctly. |

## 💰 Cost Note
* **Storage:** Minimal (Standard GCS rates).
* **Training:** ~ $3.00 / 1M tokens (Gemini Flash).
* **Inference:** Standard Gemini Flash pricing (no extra hosting fee for adapters).
