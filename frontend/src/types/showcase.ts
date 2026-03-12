export type SortMode = "relevance" | "newest" | "title"

export interface ShowcaseProject {
  id: string
  projectKey: string
  projectName: string
  summary: string
  authorName: string
  authorUsername: string
  authorAvatarUrl?: string | null
  channelName: string
  guildId: string
  guildName: string
  githubUrl?: string | null
  demoUrl?: string | null
  sourceUrl: string
  attachmentUrls: string[]
  previewImageUrl?: string | null
  keywords: string[]
  createdAt: number
  score?: number | null
}

export interface ShowcaseResponse {
  title: string
  results: ShowcaseProject[]
  meta: {
    size: number
    stats: {
      projects: number
      builders: number
      githubProjects: number
      demoProjects: number
    }
    filters: {
      channels: string[]
      authors: string[]
      guilds: string[]
    }
  }
}

export interface DashboardFilters {
  query: string
  channel: string
  author: string
  hasGithub: boolean
  hasDemo: boolean
  sort: SortMode
}
