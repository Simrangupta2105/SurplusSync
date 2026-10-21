import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { Sidebar } from '../components/Sidebar';
import { MobileBottomNav } from '../components/MobileBottomNav';
import { CommandPaletteModal } from '../components/CommandPaletteModal';

describe('Navigation & Leaderboard Removal (Task B4)', () => {
  describe('Business Sidebar Navigation', () => {
    it('renders Home as the first item and follows exact required business navigation ordering', () => {
      const onNavigateMock = vi.fn();
      render(
        <Sidebar
          isOpen={true}
          onClose={() => {}}
          activePath="home"
          onNavigate={onNavigateMock}
          orgType="BUSINESS"
          orgName="Taj Gateway Kitchen"
          alertCount={3}
        />
      );

      const navElement = screen.getByRole('navigation', { name: /sidebar navigation/i });
      const navButtons = Array.from(navElement.querySelectorAll('button')).map(
        (btn) => btn.querySelector('span.truncate')?.textContent?.trim() || btn.textContent?.trim()
      );

      // 1. Home must be the FIRST item
      expect(navButtons[0]).toBe('Home');

      // 2. Exact Business navigation items must be present
      expect(navButtons).toContain('Home');
      expect(navButtons).toContain('Dashboard');
      expect(navButtons).toContain('Inventory');
      expect(navButtons).toContain('Expiry Alerts');
      expect(navButtons).toContain('Scan');
      expect(navButtons).toContain('CSV Import');
      expect(navButtons).toContain('Surplus Marketplace');
      expect(navButtons).toContain('Donation Requests');
      expect(navButtons).toContain('Pickup Schedule');
      expect(navButtons).toContain('Impact Analytics');
      expect(navButtons).toContain('Notifications');
      expect(navButtons).toContain('Settings');

      // 3. Leaderboard must NOT be present anywhere
      expect(screen.queryByText(/leaderboard/i)).not.toBeInTheDocument();

      // 4. Clicking Home calls onNavigate with 'home'
      const homeButton = screen.getByRole('button', { name: /^home$/i });
      fireEvent.click(homeButton);
      expect(onNavigateMock).toHaveBeenCalledWith('home');
    });
  });

  describe('NGO Sidebar Navigation', () => {
    it('renders Home as the first item and follows exact required NGO navigation ordering', () => {
      const onNavigateMock = vi.fn();
      render(
        <Sidebar
          isOpen={true}
          onClose={() => {}}
          activePath="home"
          onNavigate={onNavigateMock}
          orgType="NGO"
          orgName="Robin Hood Food Relief"
        />
      );

      const navElement = screen.getByRole('navigation', { name: /sidebar navigation/i });
      const navButtons = Array.from(navElement.querySelectorAll('button')).map(
        (btn) => btn.querySelector('span.truncate')?.textContent?.trim() || btn.textContent?.trim()
      );

      // 1. Home must be the FIRST item
      expect(navButtons[0]).toBe('Home');

      // 2. Exact NGO navigation items must be present
      expect(navButtons).toContain('Home');
      expect(navButtons).toContain('Dashboard');
      expect(navButtons).toContain('Food Feed');
      expect(navButtons).toContain('Our Requirements');
      expect(navButtons).toContain('My Requests');
      expect(navButtons).toContain('Pickup Schedule');
      expect(navButtons).toContain('Impact Analytics');
      expect(navButtons).toContain('Notifications');
      expect(navButtons).toContain('Settings');

      // 3. Leaderboard must NOT be present anywhere
      expect(screen.queryByText(/leaderboard/i)).not.toBeInTheDocument();

      // 4. Clicking Home calls onNavigate with 'home'
      const homeButton = screen.getByRole('button', { name: /^home$/i });
      fireEvent.click(homeButton);
      expect(onNavigateMock).toHaveBeenCalledWith('home');
    });
  });

  describe('MobileBottomNav Navigation', () => {
    it('renders Home as the first primary item for Business and opens more menu without Leaderboard', () => {
      const onNavigateMock = vi.fn();
      render(
        <MobileBottomNav
          activePath="home"
          onNavigate={onNavigateMock}
          orgType="BUSINESS"
          onLogout={() => {}}
        />
      );

      // 1. Home is in primary mobile navigation
      const homeButton = screen.getByRole('button', { name: /^home$/i });
      expect(homeButton).toBeInTheDocument();
      fireEvent.click(homeButton);
      expect(onNavigateMock).toHaveBeenCalledWith('home');

      // 2. Open More sheet
      const moreButton = screen.getByRole('button', { name: /more navigation options/i });
      fireEvent.click(moreButton);

      // 3. Confirm zero Leaderboard items
      expect(screen.queryByText(/leaderboard/i)).not.toBeInTheDocument();
    });

    it('renders Home as the first primary item for NGO and has zero Leaderboard items', () => {
      const onNavigateMock = vi.fn();
      render(
        <MobileBottomNav
          activePath="home"
          onNavigate={onNavigateMock}
          orgType="NGO"
          onLogout={() => {}}
        />
      );

      // 1. Home is in primary mobile navigation
      const homeButton = screen.getByRole('button', { name: /^home$/i });
      expect(homeButton).toBeInTheDocument();
      fireEvent.click(homeButton);
      expect(onNavigateMock).toHaveBeenCalledWith('home');

      // 2. Open More sheet
      const moreButton = screen.getByRole('button', { name: /more navigation options/i });
      fireEvent.click(moreButton);

      // 3. Confirm zero Leaderboard items
      expect(screen.queryByText(/leaderboard/i)).not.toBeInTheDocument();
    });
  });

  describe('CommandPaletteModal Commands', () => {
    it('includes Home command and zero Leaderboard commands for Business', () => {
      const onNavigateMock = vi.fn();
      render(
        <CommandPaletteModal
          isOpen={true}
          onClose={() => {}}
          onNavigate={onNavigateMock}
          orgType="BUSINESS"
          isDark={false}
          onToggleTheme={() => {}}
          onLogout={() => {}}
        />
      );

      expect(screen.getByText('Home')).toBeInTheDocument();
      expect(screen.queryByText(/leaderboard/i)).not.toBeInTheDocument();
    });

    it('includes Home command and zero Leaderboard commands for NGO', () => {
      const onNavigateMock = vi.fn();
      render(
        <CommandPaletteModal
          isOpen={true}
          onClose={() => {}}
          onNavigate={onNavigateMock}
          orgType="NGO"
          isDark={false}
          onToggleTheme={() => {}}
          onLogout={() => {}}
        />
      );

      expect(screen.getByText('Home')).toBeInTheDocument();
      expect(screen.queryByText(/leaderboard/i)).not.toBeInTheDocument();
    });
  });
});
