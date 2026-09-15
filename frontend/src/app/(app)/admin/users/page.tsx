"use client";

import { useAdminUsers } from "@/hooks/use-admin-users";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAdminUpdateUser } from "@/hooks/use-admin-update-user";

  

export default function AdminUsersPage() {
  const { data, isLoading, isError } = useAdminUsers();
  const updateM = useAdminUpdateUser();

  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Users</h1>
        <p className="mt-1 text-sm text-muted-foreground">All registered accounts.</p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {isError && <p className="text-sm text-destructive">Failed to load.</p>}

      {data && data.items.length > 0 && (
        <div className="grid gap-3">
          {data.items.map((u) => (
            <Card key={u.id}>
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <div className="truncate font-medium text-foreground">{u.name}</div>
                  <div className="truncate text-sm text-muted-foreground">{u.email}</div>
                </div>
                                <div className="flex shrink-0 items-center gap-2">
                  {!u.is_verified && (
                    <Badge variant="secondary" className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                      Unverified
                    </Badge>
                  )}
                  <select
                    value={u.role}
                    disabled={updateM.isPending}
                    onChange={(e) => updateM.mutate({ id: u.id, role: e.target.value })}
                    className="h-8 rounded-md border border-input bg-background text-foreground px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {["student", "reviewer", "admin"].map((r) => (
                      <option key={r} value={r} className="bg-background text-foreground">{r}</option>
                    ))}
                  </select>
                  <Button
                    size="sm"
                    variant={u.is_active ? "outline" : "default"}
                    disabled={updateM.isPending}
                    onClick={() => updateM.mutate({ id: u.id, is_active: !u.is_active })}
                  >
                    {u.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}