import type { ReactNode } from "react"

import { motion } from "framer-motion"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface StatCardProps {
  label: string
  value: string
  icon: ReactNode
  className?: string
}

export function StatCard({ label, value, icon, className }: StatCardProps) {
  return (
    <motion.div whileHover={{ y: -3 }} transition={{ duration: 0.2, ease: "easeOut" }}>
      <Card
        className={cn(
          "border border-border/60 bg-card/88 shadow-[0_18px_50px_rgba(36,57,66,0.08)] backdrop-blur-sm",
          className
        )}
      >
        <CardContent className="flex items-center justify-between gap-4 pt-4">
          <div>
            <p className="font-mono text-[0.72rem] uppercase tracking-[0.24em] text-muted-foreground">
              {label}
            </p>
            <p className="mt-2 text-3xl font-bold tracking-[-0.04em] text-foreground">
              {value}
            </p>
          </div>
          <div className="rounded-full border border-border/70 bg-background/80 p-3 text-accent">
            {icon}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}
