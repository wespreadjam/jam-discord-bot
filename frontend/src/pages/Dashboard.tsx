import {
  startTransition,
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useMemo,
  useState,
} from "react"
import { motion } from "framer-motion"
import { AlertCircle, FolderSearch, LoaderCircle } from "lucide-react"

import { FilterBar } from "@/components/FilterBar"
import { ProjectCard } from "@/components/ProjectCard"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { staggerContainer, staggerItem } from "@/lib/animations"
import { ShowcaseHero } from "@/sections/ShowcaseHero"
import type {
  DashboardFilters,
  ShowcaseProject,
  ShowcaseResponse,
} from "@/types/showcase"

const initialFilters: DashboardFilters = {
  query: "",
  channel: "",
  author: "",
  hasGithub: false,
  hasDemo: false,
  sort: "relevance",
}

function buildApiUrl(path: string) {
  const configuredBase = (import.meta.env.VITE_SHOWCASE_API_BASE_URL ?? "").replace(
    /\/$/,
    ""
  )

  if (configuredBase) {
    return new URL(`${configuredBase}${path}`)
  }

  return new URL(path, window.location.origin)
}

function sortProjects(projects: ShowcaseProject[], sort: DashboardFilters["sort"]) {
  const copy = [...projects]
  if (sort === "title") {
    return copy.sort((left, right) => left.projectName.localeCompare(right.projectName))
  }
  if (sort === "newest") {
    return copy.sort((left, right) => right.createdAt - left.createdAt)
  }
  return copy
}

export function Dashboard() {
  const searchParams = useMemo(() => new URLSearchParams(window.location.search), [])
  const guildId = searchParams.get("guild_id") ?? ""
  const accessToken = searchParams.get("token") ?? ""

  const [filters, setFilters] = useState<DashboardFilters>(initialFilters)
  const [data, setData] = useState<ShowcaseResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [refreshCounter, setRefreshCounter] = useState(0)

  const deferredQuery = useDeferredValue(filters.query)

  function updateFilters(next: DashboardFilters) {
    setIsLoading(true)
    setFilters(next)
  }

  const fetchResults = useEffectEvent(async (signal: AbortSignal) => {
    const url = buildApiUrl("/api/showcase/search")
    if (guildId) {
      url.searchParams.set("guild_id", guildId)
    }
    if (accessToken) {
      url.searchParams.set("token", accessToken)
    }
    if (deferredQuery) {
      url.searchParams.set("q", deferredQuery)
    }
    if (filters.channel) {
      url.searchParams.set("channel", filters.channel)
    }
    if (filters.author) {
      url.searchParams.set("author", filters.author)
    }
    if (filters.hasGithub) {
      url.searchParams.set("has_github", "true")
    }
    if (filters.hasDemo) {
      url.searchParams.set("has_demo", "true")
    }

    const response = await fetch(url, { signal })
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { error?: string }
        | null
      throw new Error(payload?.error ?? "Search request failed.")
    }

    const payload = (await response.json()) as ShowcaseResponse
    startTransition(() => {
      setData(payload)
      setError(null)
    })
  })

  useEffect(() => {
    const controller = new AbortController()
    void fetchResults(controller.signal)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setError(reason instanceof Error ? reason.message : "Something went wrong.")
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      })

    return () => controller.abort()
  }, [
    deferredQuery,
    filters.author,
    filters.channel,
    filters.hasDemo,
    filters.hasGithub,
    refreshCounter,
  ])

  const projects = useMemo(
    () => sortProjects(data?.results ?? [], filters.sort),
    [data?.results, filters.sort]
  )

  const totalProjects = data?.meta.stats.projects ?? 0

  return (
    <div className="relative isolate overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(36,57,66,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(36,57,66,0.05)_1px,transparent_1px)] bg-[size:72px_72px] opacity-25" />
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-8 px-4 py-6 md:px-6 md:py-8 lg:px-8">
        <ShowcaseHero data={data} guildId={guildId} />

        <FilterBar
          filters={filters}
          channels={data?.meta.filters.channels ?? []}
          authors={data?.meta.filters.authors ?? []}
          totalProjects={totalProjects}
          onFiltersChange={updateFilters}
          onRefresh={() => {
            setIsLoading(true)
            setRefreshCounter((current) => current + 1)
          }}
          onReset={() => {
            setIsLoading(true)
            setFilters(initialFilters)
            setRefreshCounter((current) => current + 1)
          }}
        />

        {error ? (
          <div className="rounded-[2rem] border border-destructive/20 bg-card/90 p-6 shadow-[0_20px_50px_rgba(36,57,66,0.08)]">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-3">
                <div className="rounded-full bg-destructive/10 p-3 text-destructive">
                  <AlertCircle className="size-5" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    Search API unavailable
                  </h2>
                  <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                    {error}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                className="rounded-full px-4"
                onClick={() => {
                  setIsLoading(true)
                  setRefreshCounter((current) => current + 1)
                }}
              >
                Retry
              </Button>
            </div>
          </div>
        ) : null}

        {isLoading ? (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="rounded-[1.75rem] border border-border/60 bg-card/80 p-4 shadow-[0_18px_50px_rgba(36,57,66,0.06)]"
              >
                <Skeleton className="h-44 w-full rounded-[1.3rem]" />
                <div className="mt-4 space-y-3">
                  <Skeleton className="h-5 w-2/3 rounded-full" />
                  <Skeleton className="h-4 w-full rounded-full" />
                  <Skeleton className="h-4 w-5/6 rounded-full" />
                  <div className="flex gap-2 pt-2">
                    <Skeleton className="h-8 w-24 rounded-full" />
                    <Skeleton className="h-8 w-20 rounded-full" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {!isLoading && !error && !projects.length ? (
          <div className="flex min-h-72 flex-col items-center justify-center rounded-[2rem] border border-border/60 bg-card/84 px-6 py-16 text-center shadow-[0_18px_50px_rgba(36,57,66,0.08)]">
            <div className="rounded-full border border-border/70 bg-background/80 p-4 text-accent">
              <FolderSearch className="size-6" />
            </div>
            <h2 className="mt-5 text-2xl font-semibold tracking-[-0.03em] text-foreground">
              No projects matched those filters
            </h2>
            <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Try broadening the query, clearing one of the filters, or running the sync again if
              you recently added new project posts in Discord.
            </p>
          </div>
        ) : null}

        {!isLoading && !error && projects.length ? (
          <motion.section
            variants={staggerContainer}
            initial="hidden"
            animate="show"
            className="space-y-5"
          >
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="font-mono text-[0.72rem] uppercase tracking-[0.24em] text-muted-foreground">
                  Search results
                </p>
                <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">
                  {projects.length.toLocaleString()} projects ready to explore
                </h2>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <LoaderCircle className="size-4" />
                Live from Elasticsearch
              </div>
            </div>

            <motion.div
              variants={staggerContainer}
              className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3"
            >
              {projects.map((project) => (
                <motion.div key={project.id} variants={staggerItem}>
                  <ProjectCard project={project} />
                </motion.div>
              ))}
            </motion.div>
          </motion.section>
        ) : null}
      </div>
    </div>
  )
}
