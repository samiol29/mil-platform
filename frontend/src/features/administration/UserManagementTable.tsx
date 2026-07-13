/**
 * User & Role management table (spec 005-enterprise-platform §15, Wave 1).
 *
 * Reuses the existing virtualized `Table` primitive and the
 * `Dialog`-for-single-action / non-optimistic-mutation conventions already
 * established in `application-workspace/FindingActions.tsx` — no new
 * list/form primitives, per the design system's own reuse discipline.
 *
 * Role assignment is a real, security-relevant action (RBAC grant), so it
 * follows the same "mandatory confirm dialog, never optimistic" pattern as
 * Verify/Override/Escalate: the row's roles only change once the mutation's
 * server response comes back, never before.
 */

import type { ColumnDef } from '@tanstack/react-table';
import { useState } from 'react';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { Dialog } from '@design-system/components/Dialog';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Input } from '@design-system/components/Input';
import { Skeleton } from '@design-system/components/LoadingState';
import { Select } from '@design-system/components/Select';
import { Table } from '@design-system/components/Table';
import {
  useAdminUsers,
  useAssignRole,
  useCreateUser,
  useDeactivateUser,
} from '@entities/admin/queries';
import type { AdminUser } from '@entities/admin/types';

/** The platform's fixed RBAC role catalogue (mil.kernel.security.Role) — kept in
 * sync manually, same convention as `application-workspace/FindingActions.tsx`'s
 * `ESCALATION_TARGET_ROLES` list. */
const ASSIGNABLE_ROLES: readonly string[] = [
  'RELATIONSHIP_MANAGER',
  'VERIFICATION_OFFICER',
  'CREDIT_ANALYST',
  'UNDERWRITER',
  'RISK_ANALYST',
  'COMPLIANCE_OFFICER',
  'AUDIT_TEAM',
  'OPERATIONS_MANAGER',
  'ADMIN',
];

function CreateUserDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [externalIdentityId, setExternalIdentityId] = useState('');
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const createUser = useCreateUser();
  const addToast = useUiStore((state) => state.addToast);

  const canSubmit =
    externalIdentityId.trim().length > 0 &&
    email.trim().length > 0 &&
    displayName.trim().length > 0;

  const handleCreate = () => {
    createUser.mutate(
      { externalIdentityId, email, displayName },
      {
        onSuccess: () => {
          addToast({ title: 'User created', variant: 'success' });
          setExternalIdentityId('');
          setEmail('');
          setDisplayName('');
          onOpenChange(false);
        },
        onError: (error: unknown) => {
          addToast({
            title: 'Failed to create user',
            description: error instanceof Error ? error.message : 'Unknown error',
            variant: 'error',
          });
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Create user"
      description="Register a new platform user. Roles are assigned separately, after creation."
      primaryAction={{ label: 'Create user', onClick: handleCreate, loading: createUser.isPending }}
    >
      <div className="flex flex-col gap-3">
        <label htmlFor="admin-create-user-external-id" className="flex flex-col gap-1">
          <span className="text-label text-text-secondary">External identity id</span>
          <Input
            id="admin-create-user-external-id"
            value={externalIdentityId}
            onChange={(e) => {
              setExternalIdentityId(e.target.value);
            }}
            placeholder="idp-sub-001"
          />
        </label>
        <label htmlFor="admin-create-user-email" className="flex flex-col gap-1">
          <span className="text-label text-text-secondary">Email</span>
          <Input
            id="admin-create-user-email"
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
            }}
            placeholder="reviewer@example.com"
          />
        </label>
        <label htmlFor="admin-create-user-display-name" className="flex flex-col gap-1">
          <span className="text-label text-text-secondary">Display name</span>
          <Input
            id="admin-create-user-display-name"
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
            }}
            placeholder="Jane Reviewer"
          />
        </label>
        {!canSubmit && <p className="text-caption text-text-tertiary">All fields are required.</p>}
      </div>
    </Dialog>
  );
}

function AssignRoleDialog({
  user,
  onOpenChange,
}: {
  user: AdminUser | null;
  onOpenChange: (open: boolean) => void;
}) {
  const [roleName, setRoleName] = useState<string>(ASSIGNABLE_ROLES[0]);
  const assignRole = useAssignRole();
  const addToast = useUiStore((state) => state.addToast);

  if (user === null) return null;

  const handleAssign = () => {
    assignRole.mutate(
      { userId: user.id, roleName },
      {
        onSuccess: () => {
          addToast({ title: `${roleName} assigned`, variant: 'success' });
          onOpenChange(false);
        },
        onError: (error: unknown) => {
          addToast({
            title: 'Failed to assign role',
            description: error instanceof Error ? error.message : 'Unknown error',
            variant: 'error',
          });
        },
      },
    );
  };

  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
      title={`Assign role to ${user.displayName}`}
      primaryAction={{ label: 'Assign role', onClick: handleAssign, loading: assignRole.isPending }}
    >
      <label className="flex flex-col gap-1">
        <span className="text-label text-text-secondary">Role</span>
        <Select
          value={roleName}
          onChange={(e) => {
            setRoleName(e.target.value);
          }}
        >
          {ASSIGNABLE_ROLES.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </Select>
      </label>
    </Dialog>
  );
}

export function UserManagementTable() {
  const usersQuery = useAdminUsers();
  const deactivateUser = useDeactivateUser();
  const addToast = useUiStore((state) => state.addToast);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [roleDialogUser, setRoleDialogUser] = useState<AdminUser | null>(null);

  const handleDeactivate = (user: AdminUser) => {
    deactivateUser.mutate(user.id, {
      onSuccess: () => addToast({ title: `${user.displayName} deactivated`, variant: 'success' }),
      onError: (error: unknown) =>
        addToast({
          title: 'Failed to deactivate user',
          description: error instanceof Error ? error.message : 'Unknown error',
          variant: 'error',
        }),
    });
  };

  const columns: ColumnDef<AdminUser>[] = [
    {
      id: 'displayName',
      header: 'Name',
      accessorFn: (user) => user.displayName,
    },
    {
      id: 'status',
      header: 'Status',
      cell: (info) => (info.row.original.isActive ? 'Active' : 'Deactivated'),
    },
    {
      id: 'roles',
      header: 'Roles',
      cell: (info) =>
        info.row.original.roles.length > 0 ? info.row.original.roles.join(', ') : '—',
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: (info) => {
        const user = info.row.original;
        return (
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setRoleDialogUser(user);
              }}
            >
              Assign role
            </Button>
            <Button
              variant="danger"
              size="sm"
              disabled={!user.isActive}
              onClick={() => {
                handleDeactivate(user);
              }}
            >
              Deactivate
            </Button>
          </div>
        );
      },
    },
  ];

  if (usersQuery.isPending) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }
  if (usersQuery.isError) {
    return (
      <ErrorState
        title="Failed to load users"
        description={usersQuery.error instanceof Error ? usersQuery.error.message : 'Unknown error'}
        onRetry={() => void usersQuery.refetch()}
      />
    );
  }

  const users = usersQuery.data.items;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-heading">Users</h2>
        <Button
          variant="primary"
          onClick={() => {
            setCreateDialogOpen(true);
          }}
        >
          New user
        </Button>
      </div>
      <Table
        ariaLabel="Platform users"
        data={users}
        columns={columns}
        getRowId={(user) => user.id}
        emptyState={
          <EmptyState
            title="No users yet"
            description="Create the first platform user to get started."
          />
        }
      />
      <CreateUserDialog open={createDialogOpen} onOpenChange={setCreateDialogOpen} />
      <AssignRoleDialog
        user={roleDialogUser}
        onOpenChange={(open) => {
          if (!open) setRoleDialogUser(null);
        }}
      />
    </div>
  );
}
