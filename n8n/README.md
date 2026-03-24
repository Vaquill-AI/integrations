# Vaquill n8n and Make.com Integration

Automate legal research workflows with Vaquill's AI-powered legal research API using n8n or Make.com. This integration reads questions from a Google Sheet, sends each to the Vaquill `/ask` API, and writes answers + sources back to the sheet.

## Overview

This directory contains pre-built templates for two automation platforms:

- **n8n** (open-source, self-hostable) -- `n8n-workflow.json`
- **Make.com** (formerly Integromat, cloud-hosted) -- `make-blueprint.json`

Both templates implement the same flow:

```
Google Sheet (questions) --> Vaquill /ask API --> Google Sheet (answers + sources)
```

### Use Cases

- **Batch legal research** -- drop 50 legal questions into a sheet, get answers with cited sources in minutes
- **Automated Q&A pipelines** -- connect a form to Vaquill for instant legal research responses
- **Case law monitoring** -- schedule periodic queries about evolving legal topics
- **Due diligence checklists** -- process compliance questions in bulk against Indian case law
- **Client intake triage** -- route incoming questions through Vaquill, then forward the results to your team

## Prerequisites

1. **Vaquill account** -- sign up at [app.vaquill.ai](https://app.vaquill.ai)
2. **Vaquill API key** -- generate one in your dashboard under Settings > API Keys (starts with `vq_key_`)
3. **Google account** -- for Google Sheets access
4. **n8n instance** or **Make.com account** -- pick one

## Google Sheet Setup

Create a Google Sheet with these column headers in row 1:

| A | B | C | D | E |
|---|---|---|---|---|
| question | answer | sources | mode | status |

Add your legal questions in column A. Leave columns B-E empty -- the automation fills them in.

**Example rows:**

| question | answer | sources | mode | status |
|---|---|---|---|---|
| What is the limitation period for filing a civil suit in India? | *(filled by Vaquill)* | | | |
| Is arbitration clause valid in an unstamped agreement? | *(filled by Vaquill)* | | | |

## Vaquill API Reference

**Endpoint:**

```
POST https://api.vaquill.ai/api/v1/ask
```

**Headers:**

```
Authorization: Bearer vq_key_YOUR_API_KEY
Content-Type: application/json
```

**Request body:**

```json
{
  "question": "What is the limitation period for filing a civil suit?",
  "mode": "standard",
  "sources": ["corpus"],
  "chatHistory": []
}
```

**Parameters:**

| Field | Type | Description |
|---|---|---|
| `question` | string | The legal question to research |
| `mode` | string | `"standard"` (fast, gpt-5-mini) or `"deep"` (thorough, gpt-5.2 with multi-hop) |
| `sources` | array | `["corpus"]` for Indian case law, `["documents"]` for your uploaded docs, or both |
| `chatHistory` | array | Previous Q&A pairs for follow-up questions (empty for standalone queries) |

**Successful response (200):**

```json
{
  "data": {
    "answer": "Under the Limitation Act, 1963, the limitation period...",
    "sources": [
      {"title": "State of Punjab v. Davinder Pal Singh (2012)", "court": "Supreme Court of India"}
    ],
    "questionInterpreted": "limitation period civil suit India",
    "mode": "standard"
  },
  "meta": {
    "creditsUsed": 1,
    "creditsRemaining": 99
  }
}
```

**Error responses:**

| Status | Meaning | What to do |
|---|---|---|
| 402 | Insufficient credits | Top up at app.vaquill.ai/billing |
| 429 | Rate limit exceeded | Wait and retry (the templates handle this automatically) |
| 401 | Invalid API key | Check your key in the dashboard |

---

## Option 1: n8n Setup

### Step 1: Import the Workflow

1. Open your n8n instance (cloud or self-hosted)
2. Go to **Workflows** > **Add Workflow**
3. Click the three-dot menu (top right) > **Import from File**
4. Upload `n8n-workflow.json`
5. The workflow appears with all nodes pre-configured

### Step 2: Configure Credentials

**Google Sheets credential:**

1. Click the **New Question Added** node
2. Under **Credential to connect with**, click **Create New Credential**
3. Select **Google Sheets OAuth2 API**
4. Follow the OAuth flow to authorize your Google account
5. Save the credential

**Vaquill API key credential:**

1. Click the **Vaquill Ask API** node
2. Under **Credential to connect with**, click **Create New Credential**
3. Select **Header Auth**
4. Set:
   - **Name**: `Authorization`
   - **Value**: `Bearer vq_key_YOUR_ACTUAL_KEY`
5. Save the credential

### Step 3: Configure the Spreadsheet

1. Click the **New Question Added** node
2. Select your spreadsheet from the dropdown
3. Select the sheet (e.g., "Sheet1")
4. Repeat for **Write Answer to Sheet** and **Write Error to Sheet** nodes

### Step 4: Test and Activate

1. Add a test question in your Google Sheet (column A)
2. Click **Test Workflow** in n8n
3. Verify the answer appears in column B
4. Toggle the workflow to **Active** for automatic processing

### Workflow Nodes Explained

```
[New Question Added] --> [Filter Unanswered] --> [Vaquill Ask API] --> [Extract Response] --> [Write Answer]
                                                       |
                                                   (on error)
                                                       |
                                              [Insufficient Credits?]
                                                /              \
                                          (yes: 402)       (other error)
                                               |                |
                                       [Stop Workflow]   [Write Error to Sheet]
```

- **New Question Added** -- triggers on new rows in the Google Sheet
- **Filter Unanswered** -- skips rows that already have an answer
- **Vaquill Ask API** -- calls the `/ask` endpoint; retries automatically on 429/5xx
- **Extract Response Fields** -- pulls `answer`, `sources`, `mode` from the JSON response
- **Write Answer to Sheet** -- updates the original row with results
- **Insufficient Credits?** -- on 402, stops the workflow; on other errors, marks the row as "error"

---

## Option 2: Make.com Setup

### Step 1: Import the Blueprint

1. Log in to [make.com](https://www.make.com)
2. Click **Create a new scenario**
3. Click the three-dot menu > **Import Blueprint**
4. Upload `make-blueprint.json`
5. Click **Save**

### Step 2: Configure Google Sheets Connection

1. Click the first module (**Read Questions**)
2. Click **Add** next to Connection
3. Sign in with your Google account and grant permissions
4. Select your spreadsheet and sheet:
   - **Spreadsheet**: choose your spreadsheet
   - **Sheet Name**: select the sheet (e.g., "Sheet1")
   - **Table Contains Headers**: Yes

### Step 3: Configure the Vaquill API Key

1. Click the second module (**Call Vaquill /ask API**)
2. Find the **Authorization** header
3. Replace `YOUR_VAQUILL_API_KEY` with your actual key:
   ```
   Bearer vq_key_abc123...
   ```

### Step 4: Configure the Response Writer

1. Click the third module (**Write Answer Back**)
2. Verify the Google Sheets connection
3. Select the same spreadsheet and sheet
4. The response mapping is pre-configured:
   - Column B (answer): `{{2.data.data.answer}}`
   - Column C (sources): joined source titles
   - Column D (mode): `{{2.data.data.mode}}`
   - Column E (status): `processed`

### Step 5: Test and Schedule

1. Click **Run once** to test with existing rows
2. Check your Google Sheet for results
3. Click **Schedule** to enable automatic runs (e.g., every 15 minutes)

---

## Advanced Configuration

### Using "deep" Mode for Complex Questions

Change the request body `mode` field from `"standard"` to `"deep"` for questions that require multi-hop reasoning across multiple cases. Deep mode uses a more capable model and additional retrieval strategies but costs more credits.

### Adding Chat History for Follow-ups

To chain questions (e.g., "Tell me more about that case"), pass previous exchanges in `chatHistory`:

```json
{
  "question": "What did the court say about the burden of proof?",
  "mode": "standard",
  "sources": ["corpus"],
  "chatHistory": [
    {
      "role": "user",
      "content": "What is the limitation period for filing a civil suit?"
    },
    {
      "role": "assistant",
      "content": "Under the Limitation Act, 1963..."
    }
  ]
}
```

### Searching Your Own Documents

Set `sources` to `["documents"]` to search only your uploaded documents, or `["corpus", "documents"]` to search both Indian case law and your uploads.

### Rate Limit Handling

- **n8n**: The template retries automatically on 429 and 5xx errors (up to 2 retries with 5-second intervals)
- **Make.com**: Add a **Sleep** module (e.g., 2 seconds) between iterations if processing large batches, or enable the built-in error handler with retry

### Extending the Workflow

Both templates can be extended with additional steps:

```
Google Sheets --> Vaquill /ask --> Write Answer
                                      |
                                      +--> Slack notification
                                      +--> Email summary
                                      +--> Airtable record
                                      +--> Webhook to your app
```

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| 401 Unauthorized | Invalid or missing API key | Verify the key starts with `vq_key_` and the `Bearer ` prefix is included |
| 402 Payment Required | No credits remaining | Top up at [app.vaquill.ai/billing](https://app.vaquill.ai/billing) |
| 429 Too Many Requests | Rate limit hit | Add delays between requests; the n8n template retries automatically |
| Empty answer | Question was too vague or out of scope | Try rephrasing; check that `sources` is set correctly |
| Google Sheets auth error | OAuth token expired | Re-authenticate the Google Sheets connection |
| Workflow not triggering | Trigger not activated | In n8n, toggle the workflow to Active; in Make.com, click Schedule |

## Resources

- [Vaquill Documentation](https://docs.vaquill.ai)
- [Vaquill API Reference](https://docs.vaquill.ai/api-reference)
- [n8n Documentation](https://docs.n8n.io)
- [Make.com Documentation](https://www.make.com/en/help)
- [Google Sheets API](https://developers.google.com/sheets/api)
