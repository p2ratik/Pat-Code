# PAt Agent Dashboard

A sophisticated frontend dashboard for managing AI agents with custom models, prompts, and tools. Built with Next.js 16, Motion animations, and shadcn/ui components.

## Features

### Multi-Agent Management
- Create and manage multiple independent AI agents
- Each agent has its own model selection, system prompt, and tool configuration
- Agents are displayed in a left sidebar with quick access and selection

### Visual Canvas
- Central SVG-based canvas showing agent-to-tool relationships
- SVG connections display the hierarchy from master agent nodes to connected tools
- Real-time visual feedback with smooth Motion animations
- Agent nodes show name and selected model
- Tool nodes display real brand logos from SVG sources

### Tool Management
- Extensive library of pre-configured tools (Google Drive, GitHub, Slack, Notion, Stripe, Mailchimp, X, Zapier)
- Right-click context menu to add tools to agents
- Search functionality to filter tools by name or category
- Visual indicator for OAuth-required tools

### Configuration Panel
- Slide-out right sidebar for tool configuration
- Tool connection status display (connected/disconnected)
- OAuth authentication flow with "Connect Account" button
- Settings for tool-specific configuration
- Remove tool functionality with confirmation

### Design System
- Dark theme optimized for professional AI tool interfaces
- Inspired by Linear (information density), n8n (tool discovery), and Notion (navigation)
- Smooth 300-400ms animations throughout the interface
- Clean typography and spacing following design guidelines
- Fully responsive layout with flexbox positioning

## Architecture

### State Management
- **Zustand store** (`lib/store.ts`): Global state for agents, tools, and UI interactions
- Actions for adding/removing/updating agents and tools
- Selection state for agents and tools

### Components

#### Layout Components
- **AppHeader**: Top navigation with workspace info and controls
- **LeftSidebar**: Agent list with new agent creation
- **Canvas**: Main visual interface with SVG connections
- **ToolConfigPanel**: Right sidebar for tool configuration

#### Node Components
- **AgentNode**: Circular nodes representing agents with model info
- **ToolNode**: Tool icons with connection status indicators
- **ContextMenuPopover**: Right-click menu with tool search

#### UI Components
- shadcn/ui Button for consistent interactions
- Custom Input component with dark theme support
- Motion-powered animations for smooth transitions

### Data
- **Mock Data**: Pre-populated with 3 demo agents and various tools
- **Tools Database**: 8 available tools with OAuth requirements
- **Agent Models**: Multiple LLM options (GPT-4, Claude, etc.)

## Technologies

- **Framework**: Next.js 16 with App Router
- **Styling**: Tailwind CSS v4 (dark theme)
- **Animations**: Motion (formerly Framer Motion)
- **State**: Zustand
- **UI Components**: shadcn/ui
- **Icons**: lucide-react
- **Images**: Next.js Image optimization with real SVG logos

## File Structure

```
components/
├── ui/
│   ├── button.tsx
│   └── input.tsx
├── app-header.tsx
├── left-sidebar.tsx
├── canvas.tsx
├── agent-node.tsx
├── tool-node.tsx
├── tool-config-panel.tsx
└── context-menu-popover.tsx

lib/
├── store.ts           # Zustand state management
├── tools-data.ts      # Available tools and models
├── mock-data.ts       # Demo agents initialization
└── utils.ts           # Utility functions (cn helper)

app/
├── layout.tsx         # Root layout with dark theme
├── globals.css        # Tailwind config and theme
├── page.tsx           # Main dashboard page
```

## Key Design Decisions

### SVG Canvas
- Lightweight and performant for visual connections
- Easily animatable with Motion
- No heavy canvas library dependencies

### Three-Panel Layout
- Left sidebar for navigation (Linear-inspired)
- Center canvas for visual building (n8n-inspired)
- Right panel for configuration (clean, focused UX)

### Dark Theme
- Primary color: Deep blue (#52a3ff) for AI-forward aesthetic
- Base: Very dark grays (#09, #125) for reduced eye strain
- Borders: Subtle transparent whites for depth
- No gradients: Solid colors for professional appearance

### Animations
- 350ms slide-in for side panels
- 300ms node appear animations with stagger
- 200ms connection line draws
- 150ms hover effects
- All animations use Motion's optimized defaults

## Usage

### Creating an Agent
1. Click "New Agent" button in left sidebar
2. Agent appears with default settings
3. Click to select and manage tools

### Adding Tools to an Agent
1. Right-click on an agent node in canvas
2. Search for tools in the context menu
3. Tools appear connected to the agent with SVG lines
4. Click tool to configure settings

### Configuring a Tool
1. Click any tool node on the canvas
2. Right sidebar opens with tool details
3. View connection status
4. Configure OAuth if required
5. Customize settings
6. Click "Remove Tool" to disconnect

### Switching Agents
- Click any agent in the left sidebar
- Header updates to show selected agent
- Canvas updates to show that agent's tools

## Performance

- Fast builds with Turbopack (Next.js 16 default)
- Optimized animations with Motion
- No layout shifts with careful Tailwind usage
- Image optimization for SVG logos
- Efficient state management with Zustand

## Future Enhancements

- Backend API integration for persistence
- Real OAuth implementation for tools
- Workspace/team management
- Agent templates library
- Tool configuration validation
- Export/import agents
- Collaboration features
- Workflow history and monitoring
