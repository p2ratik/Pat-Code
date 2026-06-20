Overall Design Philosophy
Keywords
Minimal
Technical
Professional
Fast
Power-user friendly
No excessive gradients
No floating AI bubbles
No neon cyberpunk nonsense
No "AI generated illustration" style

Think somewhere between:

Linear
Vercel Dashboard
Stripe Dashboard
GitHub Settings
Supabase Admin Panel
Information Architecture
Sidebar
│
├── Chat
├── Conversations
│
├── Profiles
├── Tools
├── Users
│
├── Analytics
│
└── Settings

The user should always know:

Which profile is active
Which tools are enabled
Which model is being used
What permissions they have

These should never be hidden.

Layout Structure
Left Sidebar

Fixed.

Width ~260px.

Contains:

LOGO

Search

----------------

Chat
Conversations

----------------

Profiles
Tools
Users

----------------

Analytics

----------------

Settings

Current Profile
Current Model


Very similar to Linear.

Top Bar

Persistent.

PAT

Current Profile
▼

Current Model
▼

Status ● Online

User Avatar

This creates a feeling of control.

User should always see:

Profile: Research Agent
Model: GPT-4.1-mini

without opening settings.

Dashboard (Landing Page)

When users log in.

Not chat.

Welcome Section
Good Evening, Pratik

Research Agent is active

Stats Grid

4 cards.

Conversations
Today

Messages
Today

Tools Enabled

Current Model

Example:

154
Conversations

21
Messages

8
Tools

GPT-4.1-mini
Recent Conversations

Table.

Title
Last Activity
Messages
Quick Actions
+ New Chat

Create Profile

Manage Tools

Assign Profile

This instantly feels like software instead of a chatbot.

Chat Experience

Now the chat page.

Layout
Sidebar

Conversation List

Chat Window

Context Panel

Three-column layout.

Left

Conversation history.

Today
Yesterday
Last Week
Center

Chat.

Very clean.

Like Claude.

No huge avatars.

No colorful message bubbles.

Just:

You

message...

----------------

Agent

response...
Right Panel

This is your secret weapon.

Show runtime context.

Agent Profile
Research Agent

Model
GPT-4.1-mini

Temperature
0.7

Enabled Tools
─────────────
read_file
search_web
calculator

Conversation ID
...

This makes users feel in control.

Profile Management

Probably your most important page.

Profile List

Cards.

Research Agent

GPT-4.1-mini

7 tools

Version 3
Create Profile Modal

Minimal form.

Name

Description

Model

Temperature

Max Turns
Profile Detail Page

Example:

Research Agent

Tabs:

Overview
Tools
Versions
Assignments
Overview
Name
Description
Model
Temperature
Max Turns
Version
Tools Tab

The best UX:

Tool Marketplace style.

☑ read_file
☑ write_file
☑ search_web
☑ calculator
☐ browser

Searchable.

Toggle-based.

Save button.

Tools Page

Dedicated page.

Not hidden under profile.

Table
Name
Description
Used By

Example:

Tool	Description	Profiles
search_web	Web search	4
calculator	Math operations	7
Tool Details Drawer

When clicked.

Shows:

Tool Name

Description

Profiles Using It
User Management

Even if you're the only user today.

Build it properly.

Users Table
Name
Email
Role
Status
Profile

Actions:

Assign Profile

Assign Role

Disable User
User Detail

Tabs:

Overview
Permissions
Activity
Settings Page

Organize carefully.

General
Theme

Language

Timezone
AI Defaults
Default Model

Default Temperature

Max Turns
Security

Future-ready.

API Tokens

Sessions

MFA

Placeholder today.

Conversation Management

Don't bury conversations inside chat.

Have a dedicated page.

Table View
Conversation
Profile
Created
Messages

Click →

Opens conversation.

Extra actions:

Rename
Archive
Delete
Analytics

Later.

But reserve the page now.

Cards:

Total Users

Total Conversations

Most Used Profile

Most Used Tool

Charts:

Messages/day

Conversations/day

Tool Usage
Design System
Colors

Background:

#0A0A0A

or

#FFFFFF

depending on theme.

Accent:

Single accent.

Examples:

#2563EB

or

#4F46E5

No rainbow gradients.

Typography

Use:

Inter
Geist
IBM Plex Sans

Geist would fit perfectly with Next.js.

Radius
12px

everywhere.

Shadows

Very subtle.

shadow-sm

Mostly rely on borders.

Borders

Important.

border-zinc-200

or

border-zinc-800
UX Details That Make It Feel Premium ✨
Command Palette

Ctrl + K

Search:

Conversations
Profiles
Users
Tools

Instant navigation.

Very Linear-like.

Global Search

Search everything:

Conversation IDs
Users
Profiles
Tools
Breadcrumbs

Example:

Profiles
/
Research Agent
/
Tools
Profile Switcher

Top bar dropdown.

Research Agent
Customer Support Agent
Research Agent V2

Switch instantly.