# VoiceCab VoiceAI

## Overview

This project implements a voice-based AI taxi assistant using LiveKit agents. The agent helps customers book rides, check ride status, report lost items, and cancel rides. It leverages Google STT, TTS, and LLM services for voice interactions.

## Installation

Ensure you have `uv` installed. Then, install the required dependencies:

```sh
uv venv
source .venv/bin/activate
uv sync
```

## Environment Setup

Copy `.env.example` to `.env.local` and update the necessary environment variables:

```sh
cp .env.example .env.local
```

Modify `.env.local` with your API keys and credentials.

### Required Credentials

You need to obtain a `credentials.json` file from Google Cloud Authentication. You can get it from the following link:
[Google Cloud Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts/details/100186742818878801000;edit=true/keys?invt=Abqx0g&project=gen-lang-client-0780152816&rapt=AEjHL4MY1ZrNfbZhKKmQxuiQIidR2liqXWC7Xnp2BJQ8K_xYo6t9ZZIh1_J1F9tv9UF_SdflpNYFyRXICULN6S9PKxqhhXDLaA3cg-SLp04N3tgU712sRko)

### Example `.env` File

Create a `.env.local` file and include the following variables:

```ini
LIVEKIT_API_KEY=""
LIVEKIT_API_SECRET=""
LIVEKIT_URL="wss://navi-app-hlwfg5aq.livekit.cloud"
GOOGLE_API_KEY=""
```

## Running the App

To start the voice agent, use the following command:

```sh
uv run main.py dev
```
