/**
 * Collaboration entities (spec 005-enterprise-platform §9).
 *
 * A comment discusses one Finding's review — matches
 * `ReviewComment` (`review_session_id`-scoped), not an application-wide
 * thread (ground truth confirmed against `src/mil/review/models.py` before
 * this module was built; corrected from an earlier, wider spec draft).
 */

import { z } from 'zod';

export const reviewCommentSchema = z.object({
  id: z.uuid(),
  reviewSessionId: z.uuid(),
  authorUserId: z.uuid(),
  commentText: z.string(),
  mentionedUserIds: z.array(z.string()),
  editedAt: z.iso.datetime().nullable(),
  deletedAt: z.iso.datetime().nullable(),
  createdAt: z.iso.datetime(),
});

export type ReviewComment = z.infer<typeof reviewCommentSchema>;
