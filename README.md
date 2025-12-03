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
│       ├── tune-model.yml     # Main CI/CD pipeline definition
│       └── count-tokens.yml   # Token counting & cost estimation workflow
├── data/
│   ├── training.jsonl         # Default training dataset
│   └── raw/                   # Raw data before processing
├── scripts/
│   ├── validate_jsonl.sh      # Helper to verify JSONL format
│   └── count_tokens.py        # Token counter using Google GenAI SDK
└── README.md
```

## 🛠️ Prerequisites

1.  **Google Cloud Project** with billing enabled.
2.  **Vertex AI API** enabled (`aiplatform.googleapis.com`).
3.  **Cloud Storage Bucket** created in `us-central1`.
4.  **Python 3.10+** (for local token counting: `pip install -r requirements.txt`).

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
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == '${GITHUB_USER}'"

# 4. Bind GitHub User to Service Account (Master Key)
# Get Pool ID
POOL_ID=$(gcloud iam workload-identity-pools describe $POOL_NAME --location="global" --format="value(name)")

# Allow all repos owned by your user to use this service account
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository_owner/${GITHUB_USER}"
```

### 2. GitHub Secrets

Add the following secrets to your repository (**Settings** -> **Secrets and variables** -> **Actions**):

| Secret Name | Value Description |
| :--- | :--- |
| `GCP_SERVICE_ACCOUNT` | The email address of the service account created above (e.g., `github-trainer@PROJECT_ID.iam.gserviceaccount.com`). |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | The full resource name of the provider (e.g., `projects/123.../providers/github-provider`). |
| `GCP_TRAINING_BUCKET_NAME` | The name of your bucket (e.g., `vertex-ai-training-your-project`). |

> **Note:** The project ID is automatically extracted from the service account email, so no separate `GCP_PROJECT_ID` secret is needed.

---

## 🏃 Usage

### 1. Prepare Your Data
Replace the sample `data/training.jsonl` with your own training examples.

**Example Format:**
```json
{"systemInstruction": {"role": "system", "parts": [{"text": "You are a code auditor."}]}, "contents": [{"role": "user", "parts": [{"text": "print('hello')"}]}, {"role": "model", "parts": [{"text": "{\"review\": \"Passed\"}"}]}]}
```

**Validation:** Before pushing, validate your JSONL file using the provided validation script:
```bash
# Validate a specific file
./scripts/validate_jsonl.sh data/training.jsonl

# Or validate all .jsonl files in data/ folder
./scripts/validate_jsonl.sh
```

> **Note:** The repository includes sample training data and a validation script to help you get started quickly.

### 2. Trigger Training
1.  Go to the **Actions** tab in GitHub.
2.  Select **"⚙️ Fine-Tune Gemini (CLI MLOps)"**.
3.  Click **Run workflow**.
4.  Optionally configure:
    - **Dataset path**: Default is `data/training.jsonl`
    - **Model name**: Default is `gemini-2.0-flash-001`
    - **Epochs**: Default is 3 (recommended for most use cases)

### 3. Monitor
* **GitHub:** The workflow will finish in ~30 seconds (Fire-and-forget). It will print the **Job ID**.
* **Vertex AI Console:** Go to **Vertex AI** -> **Model Tuning** to watch the job progress.

### 4. Estimate Training Costs (Optional)
Before running a tuning job, you can estimate the token count and cost:
1.  Go to the **Actions** tab in GitHub.
2.  Select **"💰 Estimate Training Cost (Tokens)"**.
3.  Click **Run workflow** and specify your dataset path.
4.  The workflow will output total tokens and estimated cost.

---

## 🧪 Testing Your Model

Once the tuning job completes successfully, you need to deploy your tuned model to an endpoint before you can test it.

### Deploy to Endpoint

1. Go to **Vertex AI Console** → **Model Registry** → Find your tuned model
2. Click **Deploy to endpoint**
3. Create a new endpoint or use an existing one
4. Wait for deployment to complete (~5-10 minutes)

### Test via Endpoint

```bash
# Set your environment variables
export PROJECT_ID="your-project-id"
export LOCATION="us-central1"
export ENDPOINT_ID="1234567890123456789"  # Get this from the endpoint details page

# Test the deployed model
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/endpoints/${ENDPOINT_ID}:generateContent" \
  -d '{
    "system_instruction": {
      "parts": [
        { "text": "You are a code review policy enforcement model. Analyze the Python code snippet provided by the user and respond ONLY with a single JSON object. If the code is correct, output {\"review\": \"Passed\"}. If it violates a rule, output {\"rule_violation\": \"[CODE]\", \"severity\": \"[LEVEL]\", \"suggestion\": \"[EXPLANATION]\"}" }
      ]
    },
    "contents": [
      {
        "role": "user",
        "parts": [
          { "text": "def MyFunction(): return True" }
        ]
      }
    ],
    "generation_config": {
      "temperature": 0.0,
      "response_mime_type": "application/json"
    }
  }'
```

**Tips:**
- You can find the `ENDPOINT_ID` in the Vertex AI Console under **Online Prediction** → **Endpoints**.
- For production use, consider setting up monitoring and logging for your endpoint.
- Endpoints incur costs even when not in use; undeploy when not needed to save costs.

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
