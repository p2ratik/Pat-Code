# PAT v2 Product Requirements Document

## Product Name

PAT (Personal Agent Terminal)

## Vision

PAT is a personal AI operating system capable of reasoning, using tools, accessing external systems through MCPs, maintaining long-term memory, and interacting through multiple channels including Terminal, WhatsApp, Discord, and Web.

The primary goal is to create a persistent AI assistant that can act as the user's second brain, execute tasks, remember context across sessions, and continuously improve its effectiveness through memory and experience.

---

# Current State

PAT currently supports:

* Agentic reasoning loop
* Tool calling
* MCP integration
* Session management
* Context compression
* SQLite storage
* FAISS-based memory
* Streaming responses
* Approval workflows
* Long-running reasoning loops
* Tool result ingestion
* Context pruning

The current interface is terminal-based.

---

# Future State

PAT should evolve into a cloud-hosted agent platform capable of:

* Multi-user support
* Role-based access control
* WhatsApp integration
* Dynamic MCP configuration
* Persistent memory
* File processing
* Admin dashboard
* Agent observability
* Background workflow execution

---

# Core Principles

## Tool-First Architecture

PAT should solve problems through tools whenever appropriate.

The LLM is responsible for planning and reasoning.

Tools are responsible for execution.

## Memory-Driven Intelligence

PAT should improve over time by remembering:

* User preferences
* Project information
* Completed tasks
* Failure patterns
* Successful workflows

## Explainability

Agent decisions should be traceable.

Every significant reasoning step should be inspectable.

## Security First

The LLM never controls permissions.

Permissions are enforced by the backend.

---

# User Roles

## Super Admin

PAT Owner

Capabilities:

* Full MCP access
* Memory editing
* Tool management
* Dashboard access
* Agent configuration
* User management

## User

Capabilities:

* Chat
* Knowledge retrieval
* Limited tools

Permissions are assigned through role mappings.

---

# Multi-Channel Support

## Phase 1

Terminal

## Phase 2

WhatsApp

## Phase 3

Discord

## Phase 4

Web Interface

All interfaces must communicate with the same PAT Core.

---

# System Architecture

Interfaces

* Terminal
* WhatsApp
* Discord
* Dashboard

↓

PAT Core

↓

Reasoning Layer

↓

Tool Registry

↓

Memory Layer

↓

MCP Layer

↓

Storage Layer

---

# PAT Core

PAT Core is the central execution engine.

Responsibilities:

* Reasoning
* Tool execution
* Context management
* Memory retrieval
* Session state
* MCP invocation

All interfaces must invoke PAT Core.

---

# Agent Execution Model

Agent execution follows:

User Message

↓

Reasoning

↓

Tool Selection

↓

Tool Execution

↓

Tool Result

↓

Updated Context

↓

Reasoning

↓

Response

Repeat until complete.

Maximum turns configurable.

---

# Memory System

PAT Memory consists of:

## Conversation Memory

Recent messages used for context.

Stored in PostgreSQL.

## Long-Term Memory

Persistent knowledge about:

* User
* Projects
* Preferences
* Workflows

Stored in PostgreSQL + Qdrant.

## Episodic Memory

Stores experiences.

Examples:

* Successful task completions
* Repeated user requests
* Important project milestones

## Procedural Memory

Stores patterns of execution.

Examples:

* How tasks are solved
* Successful workflows
* Common tool sequences

---

# Memory Generation

Memory should not be generated after every interaction.

A dedicated Memory Summarizer should decide:

* What is important
* What should be ignored
* What should be stored

Memory generation must be separated from the main agent.

---

# Task Completion Summaries

After task completion:

PAT should generate a structured summary.

Example:

Task:
Generate project report

Steps:

* Read Notion
* Read Calendar
* Generate Summary

Outcome:
Success

Lessons:
User prefers concise reports

This summary becomes candidate memory.

---

# Failure Learning System

PAT should learn from failures.

Examples:

Tool failed:
Notion MCP timeout

Recovery:
Retry successful after 2 attempts

Stored memory:

"When Notion timeout occurs, retry before aborting."

These memories become retrievable during future executions.

---

# Few-Shot Behavioral Examples

PAT should maintain a curated example library.

Examples include:

* Planning behavior
* Tool usage
* Error recovery
* User communication style
* Approval requests

Examples are stored separately from system prompts.

Future versions should support dynamic retrieval of examples.

---

# MCP Management

Current:

config.toml

Future:

Database-driven MCP registry

Requirements:

* Connect MCPs through Dashboard
* OAuth support
* Dynamic loading
* Token management
* Scope management

Supported MCPs:

* Notion
* Gmail
* Google Drive
* Google Calendar
* Google People
* Google Chat
* Eraser
* Future MCPs

---

# MCP Credential Storage

Requirements:

* Access tokens encrypted
* Refresh tokens encrypted
* Automatic refresh
* Secret rotation support

Tokens must never be exposed to the LLM.

---

# File Handling

Supported Sources:

* WhatsApp uploads
* Dashboard uploads
* Future integrations

Flow:

Upload

↓

Temporary Storage

↓

Validation

↓

S3

↓

Metadata Storage

↓

Agent Processing

Supported Formats:

* PDF
* DOCX
* TXT
* CSV
* Images

---

# Database Requirements

Core Tables:

users

roles

user_roles

user_channels

conversations

messages

memories

agent_runs

agent_steps

agent_checkpoints

files

artifacts

mcp_servers

mcp_connections

mcp_credentials

mcp_configs

audit_logs

---

# Agent Runs

Each execution becomes an Agent Run.

Tracks:

* User
* Conversation
* Start time
* End time
* Status

Statuses:

* queued
* running
* completed
* failed

---

# Agent Steps

Each significant step is logged.

Examples:

Reasoning

Tool Call

Tool Failure

Checkpoint

Completion

Purpose:

* Debugging
* Observability
* Analytics

Large payloads should not be stored directly.

Store references instead.

---

# Checkpointing

Current:

Session-based checkpoints

Future:

Persistent checkpoints

Purpose:

* Crash recovery
* Workflow resumption
* Long-running tasks

Checkpoint frequency:

Meaningful state transitions only.

Not every token.

---

# Observability

PAT should expose:

* Tool call counts
* Tool failures
* MCP latency
* Token usage
* Memory retrieval counts
* Agent execution duration

Future:

Grafana dashboards

Prometheus metrics

---

# Security Requirements

Never trust client payloads.

Authentication:

* WhatsApp identity verification
* JWT authentication
* OAuth validation

Authorization:

* Role checks
* Tool permission checks
* MCP ownership validation

The LLM cannot bypass permissions.

---

# Admin Dashboard

Capabilities:

* Connect MCPs
* View conversations
* View memories
* Inspect agent runs
* View tool failures
* Manage users
* Configure PAT

---

# WhatsApp Integration

Owner Mode:

Full PAT capabilities.

Normal User Mode:

Restricted capabilities.

User identity derived from verified WhatsApp number.

Never from request payload.

---

# Background Worker System (Future)

Not required in initial release.

Future architecture:

API

↓

Queue

↓

Workers

↓

Agent Execution

Use Cases:

* Long-running workflows
* Research tasks
* Large document processing
* Monitoring jobs

Potential Technologies:

* Redis
* Celery
* RQ

---

# Success Criteria

PAT should be able to:

1. Operate through Terminal and WhatsApp.

2. Maintain long-term memory.

3. Dynamically use MCP tools.

4. Learn from task successes and failures.

5. Recover from crashes.

6. Support multiple users.

7. Provide secure access control.

8. Evolve into a scalable agent platform.

PAT should become a reliable personal operating system rather than a single-session chatbot.

Agent Event

     ↓

 ┌──────────────┐
 │ Event Bus    │
 └──────────────┘

     ↓
 ┌────┼────┬─────┐
 ↓    ↓    ↓
DB  Logs Metrics

Agent
 ↓
AgentEvent
 ↓
EventBus
 ↓
Subscribers

DatabaseRecorder

MetricsRecorder

AuditRecorder

MemoryRecorder

DashboardStreamer