import { motion } from "framer-motion"
import {
  ExternalLink,
  Github,
  Globe,
  MessageSquareShare,
  Paperclip,
} from "lucide-react"

import { IconButton } from "@/components/IconButton"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import type { ShowcaseProject } from "@/types/showcase"

interface ProjectCardProps {
  project: ShowcaseProject
}

function initialsFromName(name: string) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}

export function ProjectCard({ project }: ProjectCardProps) {
  const createdAt = new Date(project.createdAt * 1000)

  return (
    <motion.article
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="h-full"
    >
      <Card className="relative h-full border border-border/60 bg-card/90 shadow-[0_22px_60px_rgba(36,57,66,0.08)] backdrop-blur-sm">
        {project.previewImageUrl ? (
          <div className="relative h-52 overflow-hidden rounded-t-xl border-b border-border/60">
            <img
              src={project.previewImageUrl}
              alt={project.projectName}
              className="h-full w-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-primary/65 via-primary/15 to-transparent" />
            <div className="absolute inset-x-4 bottom-4 flex items-center justify-between gap-3">
              <Badge className="rounded-full bg-background/85 px-3 py-1 text-[0.7rem] font-mono uppercase tracking-[0.22em] text-foreground backdrop-blur-sm">
                #{project.channelName}
              </Badge>
              <span className="font-mono text-[0.72rem] text-background/90">
                {createdAt.toLocaleDateString()}
              </span>
            </div>
          </div>
        ) : null}

        <CardHeader className="gap-4">
          <div className="flex items-start gap-3">
            <Avatar className="size-11 border border-border/70 shadow-sm">
              <AvatarImage src={project.authorAvatarUrl ?? undefined} alt={project.authorName} />
              <AvatarFallback className="bg-secondary text-secondary-foreground">
                {initialsFromName(project.authorName)}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">{project.authorName}</p>
              <p className="truncate font-mono text-[0.74rem] uppercase tracking-[0.18em] text-muted-foreground">
                @{project.authorUsername}
              </p>
            </div>
            <CardAction className="flex gap-2">
              <IconButton
                href={project.sourceUrl}
                icon={<MessageSquareShare className="size-4" />}
                label="Open Discord post"
              />
            </CardAction>
          </div>
          <div className="space-y-2">
            <CardTitle className="text-xl font-bold tracking-[-0.03em] text-foreground">
              {project.projectName}
            </CardTitle>
            {!project.previewImageUrl ? (
              <div className="flex flex-wrap items-center gap-2">
                <Badge className="rounded-full bg-secondary/85 px-3 py-1 text-[0.68rem] font-mono uppercase tracking-[0.2em] text-secondary-foreground">
                  #{project.channelName}
                </Badge>
                <span className="font-mono text-[0.72rem] text-muted-foreground">
                  {createdAt.toLocaleDateString()}
                </span>
              </div>
            ) : null}
          </div>
        </CardHeader>

        <CardContent className="flex flex-1 flex-col gap-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {project.summary || "No summary extracted from the post yet."}
          </p>
          {project.keywords.length ? (
            <div className="flex flex-wrap gap-2">
              {project.keywords.slice(0, 4).map((keyword) => (
                <Badge
                  key={keyword}
                  variant="outline"
                  className="rounded-full border-border/70 bg-background/70 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground"
                >
                  {keyword}
                </Badge>
              ))}
            </div>
          ) : null}
          {project.attachmentUrls.length ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Paperclip className="size-4 text-accent" />
              <span>{project.attachmentUrls.length} asset attachment(s)</span>
            </div>
          ) : null}
        </CardContent>

        <Separator className="mx-4 w-auto bg-border/60" />

        <CardFooter className="mt-auto flex flex-wrap items-center justify-between gap-3 bg-transparent">
          <div className="flex flex-wrap gap-2">
            {project.githubUrl ? (
              <Button asChild variant="default" className="rounded-full px-4">
                <a href={project.githubUrl} target="_blank" rel="noreferrer">
                  <Github className="size-4" />
                  GitHub
                </a>
              </Button>
            ) : null}
            {project.demoUrl ? (
              <Button asChild variant="secondary" className="rounded-full px-4">
                <a href={project.demoUrl} target="_blank" rel="noreferrer">
                  <Globe className="size-4" />
                  Live
                </a>
              </Button>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <IconButton
              href={project.githubUrl ?? project.demoUrl ?? project.sourceUrl}
              icon={<ExternalLink className="size-4" />}
              label="Open primary link"
            />
          </div>
        </CardFooter>
      </Card>
    </motion.article>
  )
}
