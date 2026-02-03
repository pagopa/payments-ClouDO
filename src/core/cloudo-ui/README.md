# Cloudo UI

Cloudo UI is the management dashboard for the Cloudo Orchestrator. It provides a user-friendly interface to manage runbooks, monitor executions, handle approvals, and configure system settings.

Built with [Next.js](https://nextjs.org), [HeroUI](https://heroui.com), and [Tailwind CSS](https://tailwindcss.com).

## Features

- **Executions Monitoring**: Track and view the history of all runbook executions.
- **Approvals Management**: Review and approve/reject pending operations.
- **Smart Routing**: Configure and manage routing rules for runbook requests.
- **Workers Registry**: Monitor registered workers and their capabilities.
- **Schedule Management**: Create and manage automated runbook schedules.
- **Studio**: Visual editor for runbook schemas and workflows.
- **User Management**: Manage operators and roles.
- **Audit Logs**: Comprehensive logging of all system activities.
- **Google SSO Integration**: Secure authentication using Google accounts.

## Getting Started

### Prerequisites

- Node.js 20.x or higher
- npm, yarn, pnpm, or bun

### Configuration

Copy the `.env.local.example` file to `.env.local` and fill in the required environment variables:

```bash
cp .env.local.example .env.local
```

Required variables:

- `API_URL`: The base URL of the Cloudo Orchestrator API (e.g., your Azure Function URL).
- `CLOUDO_KEY`: The internal authentication token for Cloudo services.
- `FUNCTION_KEY`: The default access key for the Azure Function.
- `GOOGLE_CLIENT_ID`: (Optional) Google SSO Client ID for authentication.

### Installation

Install the dependencies:

```bash
npm install
```

### Development

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the results.

## Deployment

### Docker

The project includes a `Dockerfile` for containerized deployment. To build and run the container:

```bash
docker build -t cloudo-ui .
docker run -p 3000:3000 --env-file .env.local cloudo-ui
```

The application is configured for standalone output, making it optimized for container environments.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.
