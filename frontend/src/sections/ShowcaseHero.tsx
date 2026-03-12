import { motion } from "framer-motion"
import { FolderKanban, Github, Globe, Users } from "lucide-react"

import { StatCard } from "@/components/StatCard"
import { Badge } from "@/components/ui/badge"
import type { ShowcaseResponse } from "@/types/showcase"

interface ShowcaseHeroProps {
  data: ShowcaseResponse | null
  guildId: string
}

export function ShowcaseHero({ data, guildId }: ShowcaseHeroProps) {
  const stats = data?.meta.stats ?? {
    projects: 0,
    builders: 0,
    githubProjects: 0,
    demoProjects: 0,
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="relative overflow-hidden rounded-[2rem] border border-border/60 bg-card/78 px-6 py-10 shadow-[0_28px_80px_rgba(36,57,66,0.1)] backdrop-blur-xl md:px-8 md:py-12"
    >
      <div className="pointer-events-none absolute -top-14 right-0 hidden h-52 w-52 rounded-full bg-accent/30 blur-3xl md:block" />
      <div className="pointer-events-none absolute -bottom-20 left-0 hidden h-56 w-56 rounded-full bg-secondary/60 blur-3xl md:block" />

      <div className="relative grid gap-10 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <div className="flex flex-wrap gap-2">
            <Badge className="rounded-full bg-secondary px-4 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.24em] text-secondary-foreground">
              Discord to Elasticsearch to shadcn/ui
            </Badge>
            {guildId ? (
              <Badge
                variant="outline"
                className="rounded-full border-border/70 bg-background/70 px-4 py-1.5 font-mono text-[0.72rem] uppercase tracking-[0.24em] text-muted-foreground"
              >
                Guild {guildId}
              </Badge>
            ) : null}
          </div>

          <div className="space-y-4">
            <p className="font-mono text-[0.74rem] uppercase tracking-[0.28em] text-muted-foreground">
              Project command center
            </p>
            <h1 className="max-w-3xl text-4xl font-bold tracking-[-0.06em] text-foreground md:text-6xl">
              Search every shared project in the server without spelunking through channels.
            </h1>
            <p className="max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg">
              The bot scrapes project posts from your showcase channels and indexes them into
              Elasticsearch. This dashboard turns that raw Discord history into something you can
              actually query, filter, and revisit.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <StatCard
            label="Projects"
            value={stats.projects.toLocaleString()}
            icon={<FolderKanban className="size-5" />}
          />
          <StatCard
            label="Builders"
            value={stats.builders.toLocaleString()}
            icon={<Users className="size-5" />}
          />
          <StatCard
            label="GitHub"
            value={stats.githubProjects.toLocaleString()}
            icon={<Github className="size-5" />}
          />
          <StatCard
            label="Live demos"
            value={stats.demoProjects.toLocaleString()}
            icon={<Globe className="size-5" />}
          />
        </div>
      </div>
    </motion.section>
  )
}
