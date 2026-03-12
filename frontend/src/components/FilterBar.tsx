import { Search, Sparkles, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { DashboardFilters, SortMode } from "@/types/showcase"

interface FilterBarProps {
  filters: DashboardFilters
  channels: string[]
  authors: string[]
  totalProjects: number
  onFiltersChange: (next: DashboardFilters) => void
  onRefresh: () => void
  onReset: () => void
}

const sortOptions: Array<{ value: SortMode; label: string }> = [
  { value: "relevance", label: "Relevance" },
  { value: "newest", label: "Newest" },
  { value: "title", label: "A-Z" },
]

export function FilterBar({
  filters,
  channels,
  authors,
  totalProjects,
  onFiltersChange,
  onRefresh,
  onReset,
}: FilterBarProps) {
  return (
    <Card className="sticky top-4 z-20 border border-border/60 bg-card/88 shadow-[0_14px_48px_rgba(36,57,66,0.08)] backdrop-blur-xl">
      <CardContent className="space-y-4 pt-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="space-y-1">
            <p className="font-mono text-[0.72rem] uppercase tracking-[0.24em] text-muted-foreground">
              Elastic search
            </p>
            <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">
              Filter {totalProjects.toLocaleString()} indexed projects
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant={filters.hasGithub ? "default" : "outline"}
              className="rounded-full px-4"
              onClick={() =>
                onFiltersChange({ ...filters, hasGithub: !filters.hasGithub })
              }
            >
              <Sparkles className="size-4" />
              GitHub linked
            </Button>
            <Button
              type="button"
              variant={filters.hasDemo ? "secondary" : "outline"}
              className="rounded-full px-4"
              onClick={() => onFiltersChange({ ...filters, hasDemo: !filters.hasDemo })}
            >
              <Sparkles className="size-4" />
              Live demo
            </Button>
            <Button type="button" variant="outline" className="rounded-full px-4" onClick={onRefresh}>
              Refresh
            </Button>
            <Button type="button" variant="ghost" className="rounded-full px-4" onClick={onReset}>
              <X className="size-4" />
              Reset
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))]">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={filters.query}
              onChange={(event) =>
                onFiltersChange({ ...filters, query: event.target.value })
              }
              placeholder="Search projects, builders, keywords..."
              className="h-12 rounded-2xl border-border/70 bg-background/70 pl-10 shadow-none"
            />
          </div>

          <Select
            value={filters.channel || "__all__"}
            onValueChange={(value) =>
              onFiltersChange({
                ...filters,
                channel: value === "__all__" ? "" : value,
              })
            }
          >
            <SelectTrigger className="h-12 w-full rounded-2xl border-border/70 bg-background/70 px-4">
              <SelectValue placeholder="All channels" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All channels</SelectItem>
              {channels.map((channel) => (
                <SelectItem key={channel} value={channel}>
                  #{channel}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.author || "__all__"}
            onValueChange={(value) =>
              onFiltersChange({
                ...filters,
                author: value === "__all__" ? "" : value,
              })
            }
          >
            <SelectTrigger className="h-12 w-full rounded-2xl border-border/70 bg-background/70 px-4">
              <SelectValue placeholder="All builders" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All builders</SelectItem>
              {authors.map((author) => (
                <SelectItem key={author} value={author}>
                  {author}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.sort}
            onValueChange={(value) =>
              onFiltersChange({ ...filters, sort: value as SortMode })
            }
          >
            <SelectTrigger className="h-12 w-full rounded-2xl border-border/70 bg-background/70 px-4">
              <SelectValue placeholder="Sort results" />
            </SelectTrigger>
            <SelectContent>
              {sortOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  )
}
