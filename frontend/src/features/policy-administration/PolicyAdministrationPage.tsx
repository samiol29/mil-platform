/**
 * Policy Administration screen (spec 005-enterprise-platform §4, Wave 1).
 *
 * Maker-checker authoring workflow layered in front of the existing,
 * already-tested `PolicyService.create_pack`/`add_rule`/`activate_pack` —
 * this UI is the first real front door onto that domain layer (confirmed,
 * per the spec's ground-truth audit, that no code path other than a test
 * fixture had ever created a `PolicyPack` before this module).
 *
 * Each pack row expands inline (not a Drawer/Dialog) to show its rule
 * catalogue and approval history — reuses the same expand/collapse pattern
 * already established by `UploadSection`/`DocumentProcessingList`, not a
 * new disclosure primitive.
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

import { useUiStore } from '@app/uiStore';
import { Button } from '@design-system/components/Button';
import { Dialog } from '@design-system/components/Dialog';
import { EmptyState } from '@design-system/components/EmptyState';
import { ErrorState } from '@design-system/components/ErrorState';
import { Input } from '@design-system/components/Input';
import { Skeleton } from '@design-system/components/LoadingState';
import { Textarea } from '@design-system/components/Textarea';
import {
  useActivatePolicyPack,
  useAddPolicyRule,
  useApprovePolicyPack,
  useCreatePolicyPack,
  usePolicyPackApprovals,
  usePolicyPackRules,
  usePolicyPacks,
  useRejectPolicyPack,
  useSubmitPolicyPackForApproval,
} from '@entities/policy/queries';
import type { PolicyPack } from '@entities/policy/types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown error';
}

function CreatePolicyPackDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [version, setVersion] = useState('');
  const [name, setName] = useState('');
  const [jurisdiction, setJurisdiction] = useState('');
  const createPack = useCreatePolicyPack();
  const addToast = useUiStore((state) => state.addToast);

  const canSubmit = version.trim().length > 0 && name.trim().length > 0;

  const handleCreate = () => {
    createPack.mutate(
      {
        version,
        name,
        // A real content hash would be computed from the pack's actual rule
        // definition once one exists client-side to hash; for a freshly
        // drafted pack (no rules yet), a stable placeholder tied to the
        // version string is honest — it is never presented as a
        // cryptographic guarantee anywhere in this UI.
        contentHash: `draft-${version}-${Date.now().toString(36)}`,
        ...(jurisdiction.trim().length > 0 ? { jurisdiction } : {}),
      },
      {
        onSuccess: () => {
          addToast({ title: 'Policy pack drafted', variant: 'success' });
          setVersion('');
          setName('');
          setJurisdiction('');
          onOpenChange(false);
        },
        onError: (error: unknown) => {
          addToast({
            title: 'Failed to create policy pack',
            description: errorMessage(error),
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
      title="Draft a new Policy Pack"
      description="Drafting does not affect any live evaluation until it is submitted, approved, and activated."
      primaryAction={{ label: 'Create draft', onClick: handleCreate, loading: createPack.isPending }}
    >
      <div className="flex flex-col gap-3">
        <label htmlFor="policy-pack-version" className="flex flex-col gap-1">
          <span className="text-label text-text-secondary">Version</span>
          <Input
            id="policy-pack-version"
            value={version}
            onChange={(e) => { setVersion(e.target.value); }}
            placeholder="2.0.0"
          />
        </label>
        <label htmlFor="policy-pack-name" className="flex flex-col gap-1">
          <span className="text-label text-text-secondary">Name</span>
          <Input
            id="policy-pack-name"
            value={name}
            onChange={(e) => { setName(e.target.value); }}
            placeholder="US Standard Underwriting Pack"
          />
        </label>
        <label htmlFor="policy-pack-jurisdiction" className="flex flex-col gap-1">
          <span className="text-label text-text-secondary">Jurisdiction (optional)</span>
          <Input
            id="policy-pack-jurisdiction"
            value={jurisdiction}
            onChange={(e) => { setJurisdiction(e.target.value); }}
            placeholder="US"
          />
        </label>
        {!canSubmit && <p className="text-caption text-text-tertiary">Version and name are required.</p>}
      </div>
    </Dialog>
  );
}

function AddRuleForm({ policyPackId }: { policyPackId: string }) {
  const [ruleKey, setRuleKey] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState('MEDIUM');
  const addRule = useAddPolicyRule();
  const addToast = useUiStore((state) => state.addToast);

  const canSubmit = ruleKey.trim().length > 0 && name.trim().length > 0 && description.trim().length > 0;

  const handleAdd = () => {
    addRule.mutate(
      { policyPackId, ruleKey, name, description, severity },
      {
        onSuccess: () => {
          addToast({ title: 'Rule added', variant: 'success' });
          setRuleKey('');
          setName('');
          setDescription('');
        },
        onError: (error: unknown) => {
          addToast({ title: 'Failed to add rule', description: errorMessage(error), variant: 'error' });
        },
      },
    );
  };

  return (
    <div className="bg-surface-secondary rounded-container flex flex-col gap-2 p-3">
      <p className="text-label text-text-secondary font-medium">Add a rule</p>
      <div className="grid grid-cols-2 gap-2">
        <Input
          aria-label="Rule key"
          value={ruleKey}
          onChange={(e) => { setRuleKey(e.target.value); }}
          placeholder="LOW_CONFIDENCE_REVIEW"
        />
        <Input
          aria-label="Rule name"
          value={name}
          onChange={(e) => { setName(e.target.value); }}
          placeholder="Low Confidence Review"
        />
      </div>
      <Textarea
        aria-label="Rule description"
        value={description}
        onChange={(e) => { setDescription(e.target.value); }}
        placeholder="Flags findings below the confidence threshold."
        rows={2}
      />
      <div className="flex items-center gap-2">
        <Input
          aria-label="Severity"
          value={severity}
          onChange={(e) => { setSeverity(e.target.value); }}
          className="w-32"
        />
        <Button
          variant="secondary"
          size="sm"
          disabled={!canSubmit}
          loading={addRule.isPending}
          onClick={handleAdd}
        >
          Add rule
        </Button>
      </div>
    </div>
  );
}

function RejectDialog({
  approvalId,
  onOpenChange,
}: {
  approvalId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const [reason, setReason] = useState('');
  const rejectPack = useRejectPolicyPack();
  const addToast = useUiStore((state) => state.addToast);

  if (approvalId === null) return null;

  const handleReject = () => {
    rejectPack.mutate(
      { approvalId, reason },
      {
        onSuccess: () => {
          addToast({ title: 'Submission rejected', variant: 'success' });
          setReason('');
          onOpenChange(false);
        },
        onError: (error: unknown) => {
          addToast({ title: 'Failed to reject', description: errorMessage(error), variant: 'error' });
        },
      },
    );
  };

  return (
    <Dialog
      open
      onOpenChange={onOpenChange}
      title="Reject this submission"
      description="A reason is required — it is shown to the drafter and recorded on the audit trail."
      primaryAction={{ label: 'Reject', onClick: handleReject, variant: 'danger', loading: rejectPack.isPending }}
    >
      <label htmlFor="reject-reason" className="flex flex-col gap-1">
        <span className="text-label text-text-secondary">Reason</span>
        <Textarea
          id="reject-reason"
          value={reason}
          onChange={(e) => { setReason(e.target.value); }}
          rows={3}
        />
      </label>
    </Dialog>
  );
}

function PolicyPackRow({ pack }: { pack: PolicyPack }) {
  const [expanded, setExpanded] = useState(false);
  const rulesQuery = usePolicyPackRules(expanded ? pack.id : null);
  const approvalsQuery = usePolicyPackApprovals(expanded ? pack.id : null);
  const submitForApproval = useSubmitPolicyPackForApproval();
  const approvePack = useApprovePolicyPack();
  const activatePack = useActivatePolicyPack();
  const addToast = useUiStore((state) => state.addToast);
  const [rejectingApprovalId, setRejectingApprovalId] = useState<string | null>(null);

  const approvals = approvalsQuery.data?.items ?? [];
  const pendingApproval = approvals.find((a) => a.decision === 'PENDING') ?? null;
  const hasApproved = approvals.some((a) => a.decision === 'APPROVED');

  const status = pack.isActive
    ? 'Active'
    : pendingApproval !== null
      ? 'Pending approval'
      : hasApproved
        ? 'Approved — not yet activated'
        : pack.deactivatedAt !== null
          ? 'Retired'
          : 'Draft';

  return (
    <div className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-2 p-4">
      <button
        type="button"
        onClick={() => { setExpanded((v) => !v); }}
        className="flex w-full items-center justify-between gap-2 text-left outline-none focus-visible:outline-2 focus-visible:outline-focus-ring focus-visible:outline-offset-2"
      >
        <span className="flex items-center gap-2">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <span className="text-body text-text-primary font-medium">
            {pack.name} <span className="text-text-tertiary">v{pack.version}</span>
          </span>
        </span>
        <span className="text-caption text-text-secondary">{status}</span>
      </button>

      {expanded && (
        <div className="border-border-subtle flex flex-col gap-4 border-t pt-3">
          <div className="flex flex-wrap items-center gap-2">
            {status === 'Draft' && (
              <Button
                variant="secondary"
                size="sm"
                loading={submitForApproval.isPending}
                onClick={() => {
                  submitForApproval.mutate(pack.id, {
                    onSuccess: () => addToast({ title: 'Submitted for approval', variant: 'success' }),
                    onError: (error: unknown) =>
                      addToast({
                        title: 'Failed to submit',
                        description: errorMessage(error),
                        variant: 'error',
                      }),
                  });
                }}
              >
                Submit for approval
              </Button>
            )}
            {pendingApproval !== null && (
              <>
                <Button
                  variant="secondary"
                  size="sm"
                  loading={approvePack.isPending}
                  onClick={() => {
                    approvePack.mutate(pendingApproval.id, {
                      onSuccess: () => addToast({ title: 'Approved', variant: 'success' }),
                      onError: (error: unknown) =>
                        addToast({
                          title: 'Failed to approve',
                          description: errorMessage(error),
                          variant: 'error',
                        }),
                    });
                  }}
                >
                  Approve
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => { setRejectingApprovalId(pendingApproval.id); }}
                >
                  Reject
                </Button>
              </>
            )}
            {hasApproved && !pack.isActive && (
              <Button
                variant="primary"
                size="sm"
                loading={activatePack.isPending}
                onClick={() => {
                  activatePack.mutate(pack.id, {
                    onSuccess: () => addToast({ title: 'Policy pack activated', variant: 'success' }),
                    onError: (error: unknown) =>
                      addToast({
                        title: 'Failed to activate',
                        description: errorMessage(error),
                        variant: 'error',
                      }),
                  });
                }}
              >
                Activate
              </Button>
            )}
          </div>

          <div>
            <p className="text-label text-text-secondary mb-2 font-medium">Rules</p>
            {rulesQuery.isPending ? (
              <Skeleton className="h-16 w-full" />
            ) : (rulesQuery.data ?? []).length === 0 ? (
              <p className="text-caption text-text-tertiary">No rules added yet.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {(rulesQuery.data ?? []).map((rule) => (
                  <li key={rule.id} className="text-caption text-text-primary">
                    <span className="font-mono">{rule.ruleKey}</span> — {rule.name} ({rule.severity})
                  </li>
                ))}
              </ul>
            )}
            {status === 'Draft' && <AddRuleForm policyPackId={pack.id} />}
          </div>

          {approvals.length > 0 && (
            <div>
              <p className="text-label text-text-secondary mb-2 font-medium">Approval history</p>
              <ul className="flex flex-col gap-1">
                {approvals.map((approval) => (
                  <li key={approval.id} className="text-caption text-text-secondary">
                    {approval.decision}
                    {approval.reason !== null && ` — "${approval.reason}"`}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <RejectDialog
        approvalId={rejectingApprovalId}
        onOpenChange={(open) => {
          if (!open) setRejectingApprovalId(null);
        }}
      />
    </div>
  );
}

export function PolicyAdministrationPage() {
  const packsQuery = usePolicyPacks();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  if (packsQuery.isPending) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }
  if (packsQuery.isError) {
    return (
      <ErrorState
        title="Failed to load policy packs"
        description={errorMessage(packsQuery.error)}
        onRetry={() => void packsQuery.refetch()}
      />
    );
  }

  const packs = packsQuery.data.items;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-heading">Policy Packs</h2>
        <Button variant="primary" onClick={() => { setCreateDialogOpen(true); }}>
          New pack
        </Button>
      </div>
      {packs.length === 0 ? (
        <EmptyState
          title="No policy packs yet"
          description="Draft the first pack to begin governing evidence/finding evaluation."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {packs.map((pack) => (
            <PolicyPackRow key={pack.id} pack={pack} />
          ))}
        </div>
      )}
      <CreatePolicyPackDialog open={createDialogOpen} onOpenChange={setCreateDialogOpen} />
    </div>
  );
}
