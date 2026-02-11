'use client';

import { useEffect, useMemo, useState } from 'react';
import {
    getAuthorizedUsers,
    updateAuthorizedUser,
    deleteAuthorizedUser,
    syncAuthorizedUsersFromEdge,
    createAuthorizedUserWithFace,
    getGodowns
} from '@/lib/api';
import type { AuthorizedUserItem, GodownListItem } from '@/lib/types';
import { formatUtcDate } from '@/lib/formatters';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { ErrorBanner } from '@/components/ui/error-banner';
import { friendlyErrorMessage } from '@/lib/friendly-error';

export default function AuthorizedUsersPage() {
    const [users, setUsers] = useState<AuthorizedUserItem[]>([]);
    const [godowns, setGodowns] = useState<GodownListItem[]>([]);
    const [godownFilter, setGodownFilter] = useState('');
    const [roleFilter, setRoleFilter] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Add/Edit form state
    const [showForm, setShowForm] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [formData, setFormData] = useState({
        person_id: '',
        name: '',
        role: '',
        godown_id: '',
        is_active: true
    });
    const [formLoading, setFormLoading] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);
    const [formSuccess, setFormSuccess] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [fileSizeError, setFileSizeError] = useState<string | null>(null);

    // Sync state
    const [syncGodownId, setSyncGodownId] = useState('');
    const [syncing, setSyncing] = useState(false);
    const [syncMessage, setSyncMessage] = useState<string | null>(null);
    const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
    const maxUploadMb = (MAX_UPLOAD_BYTES / (1024 * 1024)).toFixed(1);
    const inlineErrorClass = 'text-xs text-red-400';

    const activeFilters = useMemo(() => {
        const chips: string[] = [];
        if (godownFilter) chips.push(`Godown: ${godownFilter}`);
        if (roleFilter) chips.push(`Role: ${roleFilter}`);
        if (statusFilter) chips.push(`Status: ${statusFilter === 'true' ? 'Active' : 'Inactive'}`);
        return chips;
    }, [godownFilter, roleFilter, statusFilter]);

    const loadUsers = async () => {
        setLoading(true);
        setError(null);
        try {
            const params: any = {};
            if (godownFilter) params.godown_id = godownFilter;
            if (roleFilter) params.role = roleFilter;
            if (statusFilter) params.is_active = statusFilter === 'true';

            const data = await getAuthorizedUsers(params);
            setUsers(data);
        } catch (e) {
            setError(
                friendlyErrorMessage(
                    e,
                    'Unable to load authorized users right now. Check your network or try again.'
                )
            );
        } finally {
            setLoading(false);
        }
    };

    const loadGodowns = async () => {
        try {
            const data = await getGodowns({});
            setGodowns(Array.isArray(data) ? data : data.items);
        } catch (e) {
            console.error('Failed to load godowns:', e);
        }
    };

    useEffect(() => {
        loadUsers();
    }, [godownFilter, roleFilter, statusFilter]);

    useEffect(() => {
        loadGodowns();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.person_id.trim() || !formData.name.trim()) return;

        setFormError(null);
        setFormSuccess(false);

        if (!editingId && !selectedFile) {
            setFormError('Photo is required to register a new authorized user.');
            return;
        }
        if (selectedFile && selectedFile.size > MAX_UPLOAD_BYTES) {
            setFormError(`Selected photo (${(selectedFile.size / 1024 / 1024).toFixed(1)} MB) exceeds the ${maxUploadMb} MB limit.`);
            return;
        }

        setFormLoading(true);

        try {
            if (editingId) {
                await updateAuthorizedUser(editingId, {
                    name: formData.name.trim(),
                    role: formData.role.trim() || null,
                    godown_id: formData.godown_id || null,
                    is_active: formData.is_active
                });
            } else {
                const formDataObj = new FormData();
                formDataObj.append('person_id', formData.person_id.trim());
                formDataObj.append('name', formData.name.trim());
                if (formData.role.trim()) formDataObj.append('role', formData.role.trim());
                if (formData.godown_id) formDataObj.append('godown_id', formData.godown_id);
                formDataObj.append('is_active', String(formData.is_active));
                formDataObj.append('file', selectedFile!);

                await createAuthorizedUserWithFace(formDataObj);
            }

            setFormSuccess(true);
            setFormData({ person_id: '', name: '', role: '', godown_id: '', is_active: true });
            setSelectedFile(null);
            setFileSizeError(null);
            setEditingId(null);
            setShowForm(false);
            await loadUsers();
            setTimeout(() => setFormSuccess(false), 3000);
        } catch (e) {
            setFormError(
                friendlyErrorMessage(
                    e,
                    'Could not save the user. Please verify your inputs and try again.'
                )
            );
        } finally {
            setFormLoading(false);
        }
    };

    const handleEdit = (user: AuthorizedUserItem) => {
        setEditingId(user.person_id);
        setFormData({
            person_id: user.person_id,
            name: user.name,
            role: user.role || '',
            godown_id: user.godown_id || '',
            is_active: user.is_active
        });
        setShowForm(true);
        setFormError(null);
        setFormSuccess(false);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const handleDelete = async (personId: string) => {
        if (!window.confirm(`Are you sure you want to delete authorized user ${personId}?`)) return;

        try {
            await deleteAuthorizedUser(personId);
            await loadUsers();
        } catch (e) {
            setError(
                friendlyErrorMessage(
                    e,
                    'Unable to delete the user right now. Please try again shortly.'
                )
            );
        }
    };

    const handleSync = async () => {
        if (!syncGodownId) {
            alert('Please select a godown to sync');
            return;
        }

        setSyncing(true);
        setSyncMessage(null);
        try {
            const result = await syncAuthorizedUsersFromEdge(syncGodownId);
            setSyncMessage(`✓ ${result.message}: Created ${result.created}, Updated ${result.updated}`);
            await loadUsers();
            setTimeout(() => setSyncMessage(null), 5000);
        } catch (e) {
            setSyncMessage(
                `✗ ${friendlyErrorMessage(
                    e,
                    'Sync failed. Check the edge connection or try again.'
                )}`
            );
        } finally {
            setSyncing(false);
        }
    };

    const roles = useMemo(() => {
        const unique = new Set(users.map(u => u.role).filter(Boolean) as string[]);
        return Array.from(unique).sort();
    }, [users]);

    const roleOptions = useMemo(() => {
        return [{ label: 'All roles', value: '' }, ...roles.map(r => ({ label: r, value: r }))];
    }, [roles]);

    const godownOptions = useMemo(() => {
        return [
            { label: 'All godowns', value: '' },
            ...godowns.map(g => ({ label: g.name || g.godown_id, value: g.godown_id }))
        ];
    }, [godowns]);

    const statusOptions = [
        { label: 'All statuses', value: '' },
        { label: 'Active', value: 'true' },
        { label: 'Inactive', value: 'false' }
    ];

    return (
        <div className="space-y-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-2">
                    <div className="hud-pill">
                        <span className="pulse-dot pulse-info" />
                        Personnel Management
                    </div>
                    <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
                        Authorized Users
                    </div>
                    <div className="text-sm text-slate-300">Manage personnel authorized to access godown facilities.</div>
                </div>
                <button
                    onClick={() => {
                        if (showForm && editingId) {
                            setEditingId(null);
                            setFormData({ person_id: '', name: '', role: '', godown_id: '', is_active: true });
                            setSelectedFile(null);
                        }
                        setShowForm(!showForm);
                    }}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors text-sm font-medium self-start lg:self-center"
                >
                    {showForm ? 'Cancel' : 'Add User'}
                </button>
            </div>

            {showForm && (
                <Card className="animate-fade-up hud-card border-blue-500/30">
                    <CardHeader>
                        <div className="text-lg font-semibold font-display">
                            {editingId ? `Edit User: ${editingId}` : 'Add New Authorized User'}
                        </div>
                        <div className="text-sm text-slate-300">
                            {editingId ? 'Update user details.' : 'Register a new authorized user in the system.'}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-400">Person ID (Required)</label>
                                    <input
                                        type="text"
                                        required
                                        disabled={!!editingId}
                                        placeholder="e.g. SH1, P1"
                                        className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                                        value={formData.person_id}
                                        onChange={(e) => setFormData({ ...formData, person_id: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-400">Name (Required)</label>
                                    <input
                                        type="text"
                                        required
                                        placeholder="e.g. John Doe"
                                        className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-400">Role</label>
                                    <input
                                        type="text"
                                        placeholder="e.g. staff, admin, security"
                                        className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                        value={formData.role}
                                        onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-400">Godown</label>
                                    <select
                                        className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                        value={formData.godown_id}
                                        onChange={(e) => setFormData({ ...formData, godown_id: e.target.value })}
                                    >
                                        <option value="">None</option>
                                        {godowns.map(g => (
                                            <option key={g.godown_id} value={g.godown_id}>
                                                {g.name || g.godown_id}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs text-slate-400">Status</label>
                                    <select
                                        className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                                        value={formData.is_active ? 'true' : 'false'}
                                        onChange={(e) => setFormData({ ...formData, is_active: e.target.value === 'true' })}
                                    >
                                        <option value="true">Active</option>
                                        <option value="false">Inactive</option>
                                    </select>
                                </div>
                                <div className="space-y-1">
                                <label className="text-xs text-slate-400">Photo (Required for new users)</label>
                                <input
                                    type="file"
                                    accept="image/*"
                                    disabled={!!editingId}
                                    required={!editingId}
                                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                                    onChange={(e) => {
                                        if (e.target.files && e.target.files[0]) {
                                            const file = e.target.files[0];
                                            if (file.size > MAX_UPLOAD_BYTES) {
                                                setSelectedFile(null);
                                                setFileSizeError(`File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max ${maxUploadMb} MB.`);
                                                return;
                                            }
                                            setSelectedFile(file);
                                            setFileSizeError(null);
                                        }
                                    }}
                                />
                                {!editingId && (
                                    <p className={inlineErrorClass}>
                                        Max image size: {maxUploadMb} MB
                                    </p>
                                )}
                                {fileSizeError && (
                                    <p className={`${inlineErrorClass} mt-1`}>
                                        {fileSizeError}
                                    </p>
                                )}
                            </div>
                            </div>

                            {formError && <ErrorBanner message={formError} />}
                            {formSuccess && (
                                <div className="text-sm text-green-400 bg-green-400/10 border border-green-400/20 rounded px-3 py-2">
                                    User {editingId ? 'updated' : 'created'} successfully!
                                </div>
                            )}

                            <div className="flex justify-end pt-2">
                                <button
                                    type="submit"
                                    disabled={formLoading}
                                    className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white rounded-md transition-colors text-sm font-medium"
                                >
                                    {formLoading ? (editingId ? 'Updating...' : 'Creating...') : (editingId ? 'Update User' : 'Create User')}
                                </button>
                            </div>
                        </form>
                    </CardContent>
                </Card>
            )}

            {/* Sync from Edge */}
            <Card className="animate-fade-up hud-card border-purple-500/30">
                <CardHeader>
                    <div className="text-lg font-semibold font-display">Sync from Edge</div>
                    <div className="text-sm text-slate-300">Import authorized users from edge known_faces.json file.</div>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-col md:flex-row gap-3 items-end">
                        <div className="flex-1 space-y-1">
                            <label className="text-xs text-slate-400">Select Godown</label>
                            <select
                                className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                                value={syncGodownId}
                                onChange={(e) => setSyncGodownId(e.target.value)}
                            >
                                <option value="">Choose a godown...</option>
                                {godowns.map(g => (
                                    <option key={g.godown_id} value={g.godown_id}>
                                        {g.name || g.godown_id}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <button
                            onClick={handleSync}
                            disabled={syncing || !syncGodownId}
                            className="px-6 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 text-white rounded-md transition-colors text-sm font-medium"
                        >
                            {syncing ? 'Syncing...' : 'Sync Now'}
                        </button>
                    </div>
                    {syncMessage && (
                        <div className={`mt-3 text-sm ${syncMessage.startsWith('✓') ? 'text-green-400 bg-green-400/10 border-green-400/20' : 'text-red-400 bg-red-400/10 border-red-400/20'} border rounded px-3 py-2`}>
                            {syncMessage}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Filters */}
            <Card className="animate-fade-up hud-card">
                <CardHeader>
                    <div className="text-lg font-semibold font-display">Filters</div>
                    <div className="text-sm text-slate-300">Filter users by godown, role, and status.</div>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div>
                            <div className="text-xs text-slate-600 mb-1">Godown</div>
                            <Select value={godownFilter} onChange={(e) => setGodownFilter(e.target.value)} options={godownOptions} />
                        </div>
                        <div>
                            <div className="text-xs text-slate-600 mb-1">Role</div>
                            <Select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} options={roleOptions} />
                        </div>
                        <div>
                            <div className="text-xs text-slate-600 mb-1">Status</div>
                            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} options={statusOptions} />
                        </div>
                    </div>

                    {activeFilters.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-4">
                            {activeFilters.map((chip) => (
                                <span key={chip} className="hud-pill">
                                    {chip}
                                </span>
                            ))}
                        </div>
                    )}

                    <div className="mt-4">
                        {error && <ErrorBanner message={error} onRetry={() => loadUsers()} />}
                        {loading ? (
                            <div className="text-sm text-slate-600">Loading…</div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-slate-700">
                                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Person ID</th>
                                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Name</th>
                                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Role</th>
                                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Godown</th>
                                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Status</th>
                                            <th className="text-left py-3 px-2 text-slate-400 font-medium">Created</th>
                                            <th className="text-right py-3 px-2 text-slate-400 font-medium">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {users.length === 0 ? (
                                            <tr>
                                                <td colSpan={7} className="text-center py-8 text-slate-500">
                                                    No authorized users found
                                                </td>
                                            </tr>
                                        ) : (
                                            users.map((user) => (
                                                <tr key={user.person_id} className="border-b border-slate-800 hover:bg-slate-800/50">
                                                    <td className="py-3 px-2 font-mono text-blue-400">{user.person_id}</td>
                                                    <td className="py-3 px-2 text-slate-200">{user.name}</td>
                                                    <td className="py-3 px-2 text-slate-300">
                                                        {user.role ? (
                                                            <span className="px-2 py-1 bg-slate-700 rounded text-xs">{user.role}</span>
                                                        ) : (
                                                            <span className="text-slate-600">—</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-2 text-slate-300">
                                                        {user.godown_id ? (
                                                            <span className="text-xs">{user.godown_id}</span>
                                                        ) : (
                                                            <span className="text-slate-600">—</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-2">
                                                        {user.is_active ? (
                                                            <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">Active</span>
                                                        ) : (
                                                            <span className="px-2 py-1 bg-slate-700 text-slate-400 rounded text-xs">Inactive</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-2 text-slate-400 text-xs">
                                                        {formatUtcDate(user.created_at)}
                                                    </td>
                                                    <td className="py-3 px-2 text-right space-x-2">
                                                        <button
                                                            onClick={() => handleEdit(user)}
                                                            className="text-blue-400 hover:text-blue-300 text-xs"
                                                        >
                                                            Edit
                                                        </button>
                                                        <button
                                                            onClick={() => handleDelete(user.person_id)}
                                                            className="text-red-400 hover:text-red-300 text-xs"
                                                        >
                                                            Delete
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                                <div className="mt-3 text-xs text-slate-500">
                                    Showing {users.length} user{users.length !== 1 ? 's' : ''}
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
