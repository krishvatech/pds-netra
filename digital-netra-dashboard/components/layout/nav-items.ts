import { Camera, LayoutGrid, Server, Settings, ShieldCheck, Users, Video } from 'lucide-react';

export type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
  adminOnly?: boolean;
  userOnly?: boolean;
};
 
export const navItems: NavItem[] = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  { href: '/dashboard/cameras', label: 'Cameras', icon: Camera },
  { href: '/dashboard/my-edges', label: 'My Edges', icon: Server, userOnly: true },
  { href: '/dashboard/live', label: 'Live Feed', icon: Video, userOnly: true },
  { href: '/dashboard/edge-devices', label: 'Edge Devices', icon: Server, adminOnly: true },
  { href: '/dashboard/users', label: 'Users', icon: Users, adminOnly: true },
  { href: '/dashboard/rule-types', label: 'Rule Types', icon: Settings, adminOnly: true },
  { href: '/dashboard/user-rule-types', label: 'User Rule Access', icon: ShieldCheck, adminOnly: true }
];

export function getNavItems(isAdmin: boolean) {
  return navItems.filter((item) => {
    if (item.adminOnly && !isAdmin) return false;
    if (item.userOnly && isAdmin) return false;
    return true;
  });
}
