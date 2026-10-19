import { describe, it, expect, beforeEach } from 'vitest';
import { demoSource } from '../services/demoSource';
import { simulationEngine } from '../simulation/simulationEngine';

describe('NGO Claim Lifecycle Flow (Demo Mode)', () => {
  beforeEach(() => {
    simulationEngine.resetData();
    demoSource.setDemoUser('NGO');
  });

  it('allows an NGO to browse available listings and submit a rescue claim', async () => {
    // 1. Fetch available listings
    const listings = await demoSource.getListings('AVAILABLE');
    expect(listings.length).toBeGreaterThan(0);

    const targetListing = listings[0];
    expect(targetListing.status).toBe('AVAILABLE');

    // 2. Submit claim with pickup ETA and vehicle/volunteer notes
    const claim = await demoSource.claimListing(
      targetListing.id,
      '20:30',
      'Pickup by refrigerated van with 2 food rescue volunteers'
    );

    expect(claim).toBeDefined();
    expect(claim.listing_id).toBe(targetListing.id);
    expect(claim.status).toBe('PENDING');
    expect(claim.pickup_eta).toBe('20:30');
    expect(claim.notes).toContain('refrigerated van');

    // 3. Target listing status should now reflect as CLAIMED
    const updatedListing = (await demoSource.getListings()).find(
      (l) => l.id === targetListing.id
    );
    expect(updatedListing?.status).toBe('CLAIMED');
  });

  it('advances claim through lifecycle: PENDING -> CONFIRMED -> PICKED_UP', async () => {
    const listings = await demoSource.getListings('AVAILABLE');
    const targetListing = listings[0];

    // Step 1: Create claim (PENDING)
    const claim = await demoSource.claimListing(targetListing.id, '21:00', 'Night rescue run');
    expect(claim.status).toBe('PENDING');

    // Step 2: Donor confirms claim (CONFIRMED)
    const confirmedClaim = await demoSource.updateClaimStatus(claim.id, 'CONFIRMED');
    expect(confirmedClaim.status).toBe('CONFIRMED');

    // Step 3: Food is collected at donor dock (PICKED_UP)
    const completedClaim = await demoSource.updateClaimStatus(claim.id, 'PICKED_UP');
    expect(completedClaim.status).toBe('PICKED_UP');

    // Listing is marked as PICKED_UP
    const listing = (await demoSource.getListings()).find((l) => l.id === targetListing.id);
    expect(listing?.status).toBe('PICKED_UP');
  });

  it('allows the NGO to rate donor partner after pickup completion', async () => {
    const listings = await demoSource.getListings('AVAILABLE');
    const claim = await demoSource.claimListing(listings[0].id, '22:00', 'Express collection');

    await demoSource.updateClaimStatus(claim.id, 'CONFIRMED');
    await demoSource.updateClaimStatus(claim.id, 'PICKED_UP');

    // Submit rating
    const ratingRes = await demoSource.rateDonor(
      claim.id,
      5,
      'Exceptional temperature control and clean food grade packaging.'
    );

    expect(ratingRes.success).toBe(true);

    const fetchedClaims = await demoSource.getClaims();
    const updatedClaim = fetchedClaims.find((c) => c.id === claim.id);
    expect(updatedClaim?.donor_rating).toBe(5);
    expect(updatedClaim?.donor_feedback).toContain('temperature control');
  });

  it('filters claims accurately by status', async () => {
    const allClaims = await demoSource.getClaims();
    expect(allClaims.length).toBeGreaterThan(0);

    const pickedUpOnly = await demoSource.getClaims('PICKED_UP');
    expect(pickedUpOnly.every((c) => c.status === 'PICKED_UP')).toBe(true);
  });
});
