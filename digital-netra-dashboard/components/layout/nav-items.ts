import { Camera, LayoutGrid, Settings, Users } from 'lucide-react';

export type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
  adminOnly?: boolean;
};

export const navItems: NavItem[] = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  { href: '/dashboard/cameras', label: 'Cameras', icon: Camera },
  { href: '/dashboard/users', label: 'Users', icon: Users, adminOnly: true },
  { href: '/dashboard/rule-types', label: 'Rule Types', icon: Settings, adminOnly: true }
];

export function getNavItems(isAdmin: boolean) {
  return navItems.filter((item) => !item.adminOnly || isAdmin);
}
