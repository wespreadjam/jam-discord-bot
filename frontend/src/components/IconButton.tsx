import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

interface IconButtonProps {
  icon: ReactNode
  label: string
  href?: string
  onClick?: () => void
  className?: string
}

export function IconButton({
  icon,
  label,
  href,
  onClick,
  className,
}: IconButtonProps) {
  const content = (
    <Button
      type="button"
      size="icon"
      variant="outline"
      onClick={onClick}
      className={cn("size-9 rounded-full bg-card/80 backdrop-blur-sm", className)}
      asChild={Boolean(href)}
    >
      {href ? (
        <a href={href} target="_blank" rel="noreferrer">
          {icon}
          <span className="sr-only">{label}</span>
        </a>
      ) : (
        <>
          {icon}
          <span className="sr-only">{label}</span>
        </>
      )}
    </Button>
  )

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      <TooltipContent sideOffset={8}>{label}</TooltipContent>
    </Tooltip>
  )
}
