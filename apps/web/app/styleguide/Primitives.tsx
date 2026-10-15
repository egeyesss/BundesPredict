"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { PlanPill } from "@/components/brand/PlanPill";

const chartConfig = {
  model: { label: "Model", color: "var(--chart-model)" },
  market: { label: "Closing market", color: "var(--chart-market)" },
  baseRate: { label: "Base rate", color: "var(--chart-base-rate)" },
} satisfies ChartConfig;

const chartData = [
  { matchday: "MD 1", model: 0.198, market: 0.191, baseRate: 0.231 },
  { matchday: "MD 2", model: 0.207, market: 0.196, baseRate: 0.228 },
  { matchday: "MD 3", model: 0.211, market: 0.203, baseRate: 0.233 },
  { matchday: "MD 4", model: 0.204, market: 0.195, baseRate: 0.229 },
];

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-3">
      <h3 className="font-mono text-xs tracking-wider text-bp-text-muted uppercase">{label}</h3>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}

export function Primitives() {
  return (
    <div className="grid gap-8">
      <Row label="Button variants">
        <Button>Start free</Button>
        <Button variant="secondary">Sign in</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="destructive">Delete chat</Button>
        <Button variant="link">Link</Button>
        <Button disabled>Disabled</Button>
      </Row>
      <Row label="Button sizes">
        <Button size="xs">Extra small</Button>
        <Button size="sm">Small</Button>
        <Button>Default</Button>
        <Button size="lg">Large</Button>
      </Row>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-2 text-sm" htmlFor="sg-email">
          Email
          <Input id="sg-email" type="email" placeholder="you@example.com" />
        </label>
        <label className="grid gap-2 text-sm" htmlFor="sg-bad">
          Invalid state
          <Input id="sg-bad" aria-invalid="true" defaultValue="not an email" />
        </label>
      </div>

      <Row label="Badges and plan pills">
        <Badge>New</Badge>
        <Badge variant="secondary">Model</Badge>
        <Badge variant="outline">Mono label</Badge>
        <Badge variant="destructive">Error</Badge>
        <PlanPill plan="free" />
        <PlanPill plan="pro" />
        <PlanPill plan="demo" />
      </Row>

      <Row label="Avatar">
        <Avatar className="size-9">
          <AvatarFallback>E</AvatarFallback>
        </Avatar>
        <Avatar size="lg">
          <AvatarFallback>D</AvatarFallback>
        </Avatar>
      </Row>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Bayern v Leipzig</CardTitle>
            <CardDescription>Saturday 18:30 Germany</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-bp-text-muted">Card on surface-1 with a hairline border.</CardContent>
        </Card>
        <Card aria-busy="true">
          <CardHeader>
            <span className="sr-only">Loading fixture</span>
            <Skeleton className="h-5 w-2/5" />
            <Skeleton className="h-3 w-3/5" />
          </CardHeader>
          <CardContent className="grid gap-2">
            <Skeleton className="h-2 w-full" />
            <Skeleton className="h-2 w-4/5" />
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="model" className="max-w-md">
        <TabsList>
          <TabsTrigger value="model">Model</TabsTrigger>
          <TabsTrigger value="news">With your news</TabsTrigger>
        </TabsList>
        <TabsContent value="model" className="text-sm text-bp-text-muted">
          Base probabilities from the fitted model.
        </TabsContent>
        <TabsContent value="news" className="text-sm text-bp-text-muted">
          Probabilities after the agent applies your news.
        </TabsContent>
      </Tabs>

      <Row label="Overlays">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="secondary">Hover for tooltip</Button>
          </TooltipTrigger>
          <TooltipContent>xG is expected goals</TooltipContent>
        </Tooltip>
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="secondary">Open dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete this chat?</DialogTitle>
              <DialogDescription>The conversation and its predictions are removed from your history.</DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="destructive">Delete</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="secondary">Open sheet</Button>
          </SheetTrigger>
          <SheetContent>
            <SheetHeader>
              <SheetTitle>Chat history</SheetTitle>
              <SheetDescription>Your recent conversations.</SheetDescription>
            </SheetHeader>
          </SheetContent>
        </Sheet>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary">Open menu</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56">
            <DropdownMenuItem>Account</DropdownMenuItem>
            <DropdownMenuItem>Manage billing</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Button variant="secondary" onClick={() => toast.success("Odds updated", { description: "Model run 42 is live." })}>
          Show toast
        </Button>
      </Row>

      <Card>
        <CardHeader>
          <CardTitle>Ranked probability score by matchday</CardTitle>
          <CardDescription>Lower is better. Chart series colours never reuse the win and lose roles.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-56 w-full">
            <BarChart accessibilityLayer data={chartData}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="matchday" tickLine={false} axisLine={false} />
              <YAxis domain={[0.15, 0.25]} tickLine={false} axisLine={false} width={44} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<ChartLegendContent />} />
              <Bar dataKey="model" fill="var(--color-model)" radius={2} isAnimationActive={false} />
              <Bar dataKey="market" fill="var(--color-market)" radius={2} isAnimationActive={false} />
              <Bar dataKey="baseRate" fill="var(--color-baseRate)" radius={2} isAnimationActive={false} />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </div>
  );
}
