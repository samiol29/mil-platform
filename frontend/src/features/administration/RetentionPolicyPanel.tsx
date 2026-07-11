/**
 * Data Retention Policy administration panel (spec 005-enterprise-platform
 * §16, Wave 4). Lives in the Administration section alongside §15's user
 * management — one governance surface, RBAC-gated per screen (the backend
 * itself rejects a save from a caller without `manage:compliance`).
 */

import { useState } from 'react';

import { Button } from '@design-system/components/Button';
import { ErrorState } from '@design-system/components/ErrorState';
import { Input } from '@design-system/components/Input';
import { Select } from '@design-system/components/Select';
import { Skeleton } from '@design-system/components/LoadingState';
import { NEVER_DELETABLE_CATEGORIES } from '@entities/compliance/types';
import { useRetentionPolicies, useSetRetentionPolicy } from '@entities/compliance/queries';

const KNOWN_CATEGORIES = ['DOCUMENT', 'AUDIT_EVENT', 'EVIDENCE', 'NOTIFICATION_LOG'];

export function RetentionPolicyPanel() {
  const policiesQuery = useRetentionPolicies();
  const setPolicyMutation = useSetRetentionPolicy();
  const [dataCategory, setDataCategory] = useState(KNOWN_CATEGORIES[0]);
  const [retentionPeriodDays, setRetentionPeriodDays] = useState(365);
  const [action, setAction] = useState<'ARCHIVE' | 'DELETE'>('ARCHIVE');

  const isDeleteDisallowed = NEVER_DELETABLE_CATEGORIES.has(dataCategory);

  if (policiesQuery.isPending) {
    return <Skeleton className="h-24 w-full" />;
  }
  if (policiesQuery.isError) {
    return (
      <ErrorState
        title="Failed to load retention policies"
        description={policiesQuery.error instanceof Error ? policiesQuery.error.message : 'Unknown error'}
        onRetry={() => void policiesQuery.refetch()}
      />
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-heading">Data Retention Policies</h2>

      {policiesQuery.data.items.length === 0 ? (
        <p className="text-caption text-text-tertiary">No retention policies configured yet.</p>
      ) : (
        <table className="text-body w-full">
          <thead>
            <tr className="text-caption text-text-tertiary border-border-default border-b text-left uppercase">
              <th className="py-1.5 font-normal">Category</th>
              <th className="py-1.5 font-normal">Retention (days)</th>
              <th className="py-1.5 font-normal">Action</th>
            </tr>
          </thead>
          <tbody className="divide-border-default divide-y">
            {policiesQuery.data.items.map((policy) => (
              <tr key={policy.id}>
                <td className="py-1.5">{policy.dataCategory}</td>
                <td className="py-1.5 tabular-nums">{policy.retentionPeriodDays}</td>
                <td className="py-1.5">{policy.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="bg-surface-raised shadow-raised rounded-container flex flex-col gap-3 p-4">
        <h3 className="text-body font-medium">Set a policy</h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-caption text-text-tertiary">Category</span>
            <Select
              value={dataCategory}
              onChange={(e) => {
                setDataCategory(e.target.value);
                if (NEVER_DELETABLE_CATEGORIES.has(e.target.value)) setAction('ARCHIVE');
              }}
            >
              {KNOWN_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1" htmlFor="retention-period-days">
            <span className="text-caption text-text-tertiary">Retention (days)</span>
            <Input
              id="retention-period-days"
              type="number"
              min={1}
              value={retentionPeriodDays}
              onChange={(e) => {
                setRetentionPeriodDays(Number(e.target.value));
              }}
            />
          </label>
          <label className="flex flex-col gap-1" htmlFor="retention-action">
            <span className="text-caption text-text-tertiary">Action</span>
            <Select
              id="retention-action"
              value={action}
              onChange={(e) => {
                setAction(e.target.value as 'ARCHIVE' | 'DELETE');
              }}
            >
              <option value="ARCHIVE">Archive</option>
              <option value="DELETE" disabled={isDeleteDisallowed}>
                Delete{isDeleteDisallowed ? ' (not permitted for this category)' : ''}
              </option>
            </Select>
          </label>
          <Button
            variant="primary"
            loading={setPolicyMutation.isPending}
            onClick={() => {
              setPolicyMutation.mutate({ dataCategory, retentionPeriodDays, action });
            }}
          >
            Save
          </Button>
        </div>
        {setPolicyMutation.isError && (
          <p className="text-caption text-feedback-error-fg">
            {setPolicyMutation.error instanceof Error
              ? setPolicyMutation.error.message
              : 'Failed to save policy.'}
          </p>
        )}
      </div>
    </section>
  );
}
