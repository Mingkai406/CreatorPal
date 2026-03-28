# 🤝 CreatorPal

**A PAL Agent for YouTube Creator-Audience Semantic Matching**

CS 6120 Natural Language Processing — Final Project
Northeastern University, Khoury College of Computer Science

## Overview

CreatorPal is an autonomous AI agent that analyzes YouTube creator channels and identifies optimal audience communities for content distribution. Powered by a ReAct-style agent loop with Gemini 2.5 Flash, the system orchestrates multiple NLP skills — semantic search, topic modeling, sentiment analysis, and program-aided reasoning — to generate actionable audience growth strategies.

## Architecture
```
User Query → LLM Agent (ReAct Loop) → Skills → Final Report
                                        ├── youtube_api
                                        ├── semantic_search (bi-encoder + cross-encoder)
                                        ├── topic_modeling (BERTopic)
                                        ├── sentiment_analysis (RoBERTa)
                                        ├── trend_analysis
                                        └── code_executor (PAL)
```

## Quick Start

### Prerequisites
- Python 3.10+
- Google AI Studio API Key ([free](https://aistudio.google.com/apikey))
- YouTube Data API Key ([free](https://console.cloud.google.com))

### Setup
```bash
git clone https://github.com/[YOUR_USERNAME]/creatorpal.git
cd creatorpal
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Run
```bash
streamlit run app/app.py
```

### Docker
```bash
docker-compose up
```

## Team
- Mingkai Gao
- Runxin Shao
- Ziqi Yang
- Gaoyuan Shi
