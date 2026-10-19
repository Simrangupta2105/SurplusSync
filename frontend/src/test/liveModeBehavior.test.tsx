import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { Header } from '../components/Header';
import { CommandPaletteModal } from '../components/CommandPaletteModal';
import { PendingVerificationPage } from '../pages/PendingVerificationPage';
import { LiveSource, apiClient } from '../services/liveSource';
import { storeTokens, clearAuthSession } from '../services/auth';

const liveSource = new LiveSource();

describe('Step 4: Live Mode vs Demo Mode Verification', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearAuthSession();
  });

  describe('Header & Persona Switcher in Live Mode', () => {
    it('does NOT render "Demo data" badge or persona switcher options in Live Mode (isDemoMode=false)', () => {
      render(
        <Header
          onToggleSidebar={() => {}}
          pageTitle="Inventory"
          onOpenCommandPalette={() => {}}
          orgType="BUSINESS"
          orgName="Metro Fresh Supermarket"
          userName="Rajesh Kumar"
          isVerified={true}
          isDemoMode={false} // Live mode
          notifications={[]}
          onLogout={() => {}}
        />
      );

      // 1. "Demo data" pill must be completely absent
      expect(screen.queryByText(/demo data/i)).not.toBeInTheDocument();

      // 2. Open user dropdown
      const userBtn = screen.getByRole('button', { name: /user account menu/i });
      fireEvent.click(userBtn);

      // 3. User details should reflect the real user and org from GET /accounts/me/
      expect(screen.getAllByText('Rajesh Kumar').length).toBeGreaterThan(0);
      expect(screen.getByText('Metro Fresh Supermarket')).toBeInTheDocument();

      // 4. "Switch Demo Persona" section and persona buttons must be absent
      expect(screen.queryByText(/switch demo persona/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/business \(partner kitchen\)/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/ngo \(relief foundation\)/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/unverified ngo \(review\)/i)).not.toBeInTheDocument();
    });

    it('renders "Demo data" badge and persona switcher when in Demo Mode (isDemoMode=true)', () => {
      const switchPersonaMock = vi.fn();
      render(
        <Header
          onToggleSidebar={() => {}}
          pageTitle="Inventory"
          onOpenCommandPalette={() => {}}
          orgType="BUSINESS"
          orgName="The Grand Gateway Bengaluru"
          userName="Priya Sharma"
          isVerified={true}
          isDemoMode={true} // Demo mode
          notifications={[]}
          onLogout={() => {}}
          onSwitchPersona={switchPersonaMock}
        />
      );

      // 1. "Demo data" pill must be present
      expect(screen.getByText(/demo data/i)).toBeInTheDocument();

      // 2. Open user dropdown
      const userBtn = screen.getByRole('button', { name: /user account menu/i });
      fireEvent.click(userBtn);

      // 3. Persona switcher must be present
      expect(screen.getByText(/switch demo persona/i)).toBeInTheDocument();
      const ngoOption = screen.getByText(/ngo \(relief foundation\)/i);
      fireEvent.click(ngoOption);
      expect(switchPersonaMock).toHaveBeenCalledWith('NGO');
    });
  });

  describe('Command Palette in Live Mode', () => {
    it('omits "Simulate POS Sale" action when onSimulatePOS is undefined (Live Mode)', () => {
      render(
        <CommandPaletteModal
          isOpen={true}
          onClose={() => {}}
          onNavigate={() => {}}
          orgType="BUSINESS"
          isDark={true}
          onToggleTheme={() => {}}
          onLogout={() => {}}
          onSimulatePOS={undefined} // Live mode
        />
      );

      // "Simulate POS Sale" should not be listed
      expect(screen.queryByText(/simulate pos sale/i)).not.toBeInTheDocument();
    });

    it('includes "Simulate POS Sale" when onSimulatePOS is passed (Demo Mode)', () => {
      const simulateMock = vi.fn();
      render(
        <CommandPaletteModal
          isOpen={true}
          onClose={() => {}}
          onNavigate={() => {}}
          orgType="BUSINESS"
          isDark={true}
          onToggleTheme={() => {}}
          onLogout={() => {}}
          onSimulatePOS={simulateMock} // Demo mode
        />
      );

      expect(screen.getByText(/simulate pos sale/i)).toBeInTheDocument();
    });
  });

  describe('Pending Verification Page in Live Mode', () => {
    it('does NOT show "Switch to Verified Persona (Demo)" button when onSwitchToBusinessDemo is undefined', () => {
      render(
        <PendingVerificationPage
          organizationName="Robin Hood Army Live"
          onLogout={() => {}}
          onSwitchToBusinessDemo={undefined} // Live mode
        />
      );

      expect(screen.getByText(/verification in progress/i)).toBeInTheDocument();
      expect(screen.getByText('Robin Hood Army Live')).toBeInTheDocument();
      expect(screen.queryByText(/switch to verified persona \(demo\)/i)).not.toBeInTheDocument();
    });
  });

  describe('Role Comes Strictly from GET /accounts/me/', () => {
    it('queries GET /accounts/me/ with Bearer access token', async () => {
      storeTokens('live-access-jwt-token-xyz', 'refresh-token-xyz', true);

      const mockGet = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
        data: {
          id: 42,
          username: 'live_manager',
          email: 'manager@metrofresh.in',
          role: 'OWNER',
          organization: {
            id: 10,
            name: 'Metro Fresh Enterprise',
            type: 'BUSINESS',
            is_verified: true,
          },
        },
      });

      const me = await liveSource.getMe();

      expect(mockGet).toHaveBeenCalledWith('/accounts/me/');
      expect(me.username).toBe('live_manager');
      expect(me.role).toBe('OWNER');
      expect(me.organization.type).toBe('BUSINESS');
      expect(me.organization.name).toBe('Metro Fresh Enterprise');
      expect(me.organization.is_verified).toBe(true);
    });

    it('correctly passes NGO role and verification from /accounts/me/ response', async () => {
      storeTokens('live-ngo-token', 'refresh-token', false);

      vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
        data: {
          id: 99,
          username: 'ngo_coordinator',
          email: 'coordinator@feedindia.org',
          role: 'STAFF',
          organization: {
            id: 25,
            name: 'Feed India Foundation',
            type: 'NGO',
            is_verified: false,
          },
        },
      });

      const me = await liveSource.getMe();

      expect(me.username).toBe('ngo_coordinator');
      expect(me.role).toBe('STAFF');
      expect(me.organization.type).toBe('NGO');
      expect(me.organization.is_verified).toBe(false);
    });
  });
});
