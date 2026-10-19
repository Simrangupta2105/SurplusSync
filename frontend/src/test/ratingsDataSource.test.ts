import { describe, it, expect, beforeEach } from 'vitest';
import { demoSource } from '../services/demoSource';
import { simulationEngine } from '../simulation/simulationEngine';

describe('Ratings Data Layer (DemoSource)', () => {
  beforeEach(() => {
    simulationEngine.resetData();
    demoSource.setDemoUser('NGO');
  });

  it('fetches pending ratings only for picked up claims of the logged-in NGO without existing ratings', async () => {
    const pending = await demoSource.getPendingRatings();
    expect(Array.isArray(pending)).toBe(true);

    // In seeded data, claim #3 is PICKED_UP for NGO #2 and unrated
    const claim3 = pending.find((p) => p.claim_id === 3);
    expect(claim3).toBeDefined();
    expect(claim3?.donor_name).toBeTruthy();
    expect(claim3?.item).toBeTruthy();

    // Claim #4 is already rated, so it must NOT be in pending ratings
    const claim4 = pending.find((p) => p.claim_id === 4);
    expect(claim4).toBeUndefined();

    // Claim #1 is CONFIRMED (not picked up), must NOT be in pending ratings
    const claim1 = pending.find((p) => p.claim_id === 1);
    expect(claim1).toBeUndefined();
  });

  it('allows verified NGO to rate a picked up claim with valid stars (1-5)', async () => {
    const newRating = await demoSource.rateClaim(3, {
      stars: 5,
      comment: 'Excellent hot food packaging, very punctual pickup!',
    });

    expect(newRating).toBeDefined();
    expect(newRating.claim).toBe(3);
    expect(newRating.stars).toBe(5);
    expect(newRating.comment).toContain('Excellent hot food');
    expect(newRating.is_editable).toBe(true);
    expect(newRating.is_hidden).toBe(false);

    // After rating, claim #3 should no longer be in pending ratings
    const pendingAfter = await demoSource.getPendingRatings();
    expect(pendingAfter.find((p) => p.claim_id === 3)).toBeUndefined();
  });

  it('rejects rating creation if stars is outside 1-5 range', async () => {
    await expect(
      demoSource.rateClaim(3, { stars: 6, comment: 'Too high' })
    ).rejects.toThrow(/stars must be between 1 and 5/i);

    await expect(
      demoSource.rateClaim(3, { stars: 0, comment: 'Too low' })
    ).rejects.toThrow(/stars must be between 1 and 5/i);
  });

  it('rejects rating if claim is not in PICKED_UP status', async () => {
    // Claim #1 is CONFIRMED
    await expect(
      demoSource.rateClaim(1, { stars: 4, comment: 'Not yet picked up' })
    ).rejects.toThrow(/picked up/i);
  });

  it('rejects duplicate ratings on the same claim', async () => {
    // Claim #4 was already rated in initial seed data
    await expect(
      demoSource.rateClaim(4, { stars: 5, comment: 'Trying to rate again' })
    ).rejects.toThrow(/already exists/i);
  });

  it('blocks unverified NGO from rating claims', async () => {
    demoSource.setDemoUser('NGO_UNVERIFIED');
    await expect(
      demoSource.rateClaim(3, { stars: 5, comment: 'Unverified attempt' })
    ).rejects.toThrow(/verified/i);
  });

  it('allows the NGO to edit an active rating within the 7-day window', async () => {
    const myRatings = await demoSource.getMyRatings();
    expect(myRatings.results.length).toBeGreaterThan(0);
    const existing = myRatings.results[0];

    const updated = await demoSource.updateRating(existing.id, {
      stars: 4,
      comment: 'Updated review note after inspection.',
    });

    expect(updated.id).toBe(existing.id);
    expect(updated.stars).toBe(4);
    expect(updated.comment).toBe('Updated review note after inspection.');
  });

  it('rejects editing if the 7-day edit window has expired', async () => {
    const internalRatings = demoSource.getInternalState().ratings;
    const target = internalRatings.find((r) => r.id === 1);
    expect(target).toBeDefined();

    if (target) {
      // Artificially simulate that edit deadline passed 1 day ago
      target.edit_deadline = new Date(Date.now() - 86400000).toISOString();
      target.is_editable = false;
    }

    await expect(
      demoSource.updateRating(1, { stars: 3, comment: 'Late edit' })
    ).rejects.toThrow(/locked|edit window/i);
  });

  it('returns business rating summary with aggregates, breakdown, and recent reviews', async () => {
    const summary = await demoSource.getBusinessRatings(1);
    expect(summary.business_id).toBe(1);
    expect(summary.rating_count).toBeGreaterThan(0);
    expect(typeof summary.rating_avg).toBe('number');
    expect(summary.breakdown).toBeDefined();
    expect(summary.breakdown['5']).toBeGreaterThanOrEqual(1);
    expect(summary.recent_reviews.length).toBeGreaterThan(0);
  });
});
