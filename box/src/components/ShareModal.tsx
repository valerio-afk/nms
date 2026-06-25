import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { X, UserPlus, Calendar, Link2, Copy, Check, Trash2, User, CheckSquare, Square, Share2, ShieldOff } from 'lucide-react';
import { shareFs, revokeShare, getAllUsers, type FileInfo, type SharingPermissions, type FileSharedInfo } from '../utils/api';

interface ShareModalProps {
    isOpen: boolean;
    onClose: () => void;
    file: FileInfo | null;
    currentPath: string;
    onShareChanged?: () => void;
}

export default function ShareModal({ isOpen, onClose, file, currentPath, onShareChanged }: ShareModalProps) {
    const { t } = useTranslation();

    const [usersList, setUsersList] = useState<string[]>([]);
    const [userInput, setUserInput] = useState('');
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [canEdit, setCanEdit] = useState(false);
    const [sharingPermissions, setSharingPermissions] = useState<SharingPermissions[]>([]);

    const [isTimeless, setIsTimeless] = useState(true);
    const [expireDate, setExpireDate] = useState('');
    const [expireTime, setExpireTime] = useState('23:59');

    const [token, setToken] = useState('');
    const [loading, setLoading] = useState(false);
    const [revoking, setRevoking] = useState(false);
    const [copied, setCopied] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const suggestionsRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Determine if editing an existing share
    const existingShare: FileSharedInfo | null = (file?.shared) ?? null;
    const isEditing = !!existingShare;

    // Fetch users when modal opens and populate from existing share data
    useEffect(() => {
        if (isOpen) {
            getAllUsers()
                .then(users => {
                    setUsersList(users);
                })
                .catch(err => {
                    console.error('Failed to load users:', err);
                });

            // Pre-populate from existing share data
            if (existingShare) {
                // Convert share_with map to SharingPermissions array
                if (existingShare.share_with) {
                    const perms: SharingPermissions[] = Object.entries(existingShare.share_with).map(
                        ([username, perm]) => ({ username, can_edit: perm.can_edit })
                    );
                    setSharingPermissions(perms);
                } else {
                    setSharingPermissions([]);
                }

                // Set expiration
                if (existingShare.expire_date) {
                    setIsTimeless(false);
                    const expDate = new Date(existingShare.expire_date * 1000);
                    setExpireDate(expDate.toISOString().split('T')[0]);
                    const hours = String(expDate.getHours()).padStart(2, '0');
                    const minutes = String(expDate.getMinutes()).padStart(2, '0');
                    setExpireTime(`${hours}:${minutes}`);
                } else {
                    setIsTimeless(true);
                    setExpireDate('');
                    setExpireTime('23:59');
                }
            }
        } else {
            // Reset state on close
            setUserInput('');
            setSharingPermissions([]);
            setIsTimeless(true);
            setExpireDate('');
            setExpireTime('23:59');
            setToken('');
            setError(null);
            setRevoking(false);
        }
    }, [isOpen]);

    // Handle clicks outside of autocomplete suggestion dropdown
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (suggestionsRef.current && !suggestionsRef.current.contains(e.target as Node) && e.target !== inputRef.current) {
                setShowSuggestions(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    if (!isOpen || !file) return null;

    const filteredUsers = usersList.filter(user =>
        user.toLowerCase().includes(userInput.toLowerCase()) &&
        !sharingPermissions.some(p => p.username === user)
    );

    const handleAddUser = (username: string) => {
        if (!username.trim()) return;
        if (sharingPermissions.some(p => p.username === username)) return;

        setSharingPermissions(prev => [...prev, { username: username.trim(), can_edit: canEdit }]);
        setUserInput('');
        setCanEdit(false);
        setShowSuggestions(false);
        setError(null);
    };

    const handleRemoveUser = (username: string) => {
        setSharingPermissions(prev => prev.filter(p => p.username !== username));
    };

    const handleToggleEdit = (username: string) => {
        setSharingPermissions(prev => prev.map(p =>
            p.username === username ? { ...p, can_edit: !p.can_edit } : p
        ));
    };

    const handleGenerateLink = async () => {
        setLoading(true);
        setError(null);

        const fullPath = currentPath ? `${currentPath}/${file.name}` : file.name;

        let expireDays: number | undefined = undefined;
        if (!isTimeless && expireDate) {
            const today = new Date();
            const selected = new Date(`${expireDate}T${expireTime || '00:00'}`);

            const diffTime = selected.getTime() - today.getTime();
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            expireDays = diffDays > 0 ? diffDays : 1;
        }

        try {
            const payload = {
                path: fullPath,
                sharing_permissions: sharingPermissions.length > 0 ? sharingPermissions : null,
                expire: expireDays !== undefined ? expireDays : null
            };
            const response = await shareFs(payload);
            setToken(response.token);
            onShareChanged?.();
        } catch (err: any) {
            console.error('Error generating link:', err);
            setError(err instanceof Error ? err.message : t('share.error_generate'));
        } finally {
            setLoading(false);
        }
    };

    const handleRevoke = async () => {
        setRevoking(true);
        setError(null);

        const fullPath = currentPath ? `${currentPath}/${file.name}` : file.name;

        try {
            await revokeShare(fullPath);
            onShareChanged?.();
            onClose();
        } catch (err: any) {
            console.error('Error revoking share:', err);
            setError(err instanceof Error ? err.message : t('share.error_revoke'));
        } finally {
            setRevoking(false);
        }
    };

    const fallbackCopyText = (text: string) => {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.position = "fixed";
        
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            } else {
                console.error('Fallback copy command was unsuccessful');
            }
        } catch (err) {
            console.error('Fallback copy failed:', err);
        }
        
        document.body.removeChild(textArea);
    };

    const handleCopyLink = () => {
        const shareableLink = getShareableLink(token);
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(shareableLink)
                .then(() => {
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                })
                .catch(err => {
                    console.error('Failed to copy link using clipboard API:', err);
                    fallbackCopyText(shareableLink);
                });
        } else {
            fallbackCopyText(shareableLink);
        }
    };

    // Get today's string in YYYY-MM-DD for min date attribute
    const todayStr = new Date().toISOString().split('T')[0];

    const getShareableLink = (token: string) => {
        const origin = `${window.location.origin}${window.location.pathname}`

        if (origin.endsWith("/")) {
            return `${origin}share?t=${token}`;
        }
        return `${origin}/share?t=${token}`;
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 dark:bg-black/50 backdrop-blur-sm">
            <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl ring-1 ring-gray-900/5 dark:ring-white/10 w-full max-w-lg p-6 animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="flex items-center justify-between pb-4 border-b border-gray-200 dark:border-zinc-800">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                        <Share2 className="w-5 h-5 text-indigo-500" />
                        {isEditing ? t('share.title_edit', { name: file.name }) : t('share.title', { name: file.name })}
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-gray-500 hover:bg-gray-100 dark:hover:bg-zinc-800 p-1.5 rounded-lg transition-colors focus:outline-none"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto py-4 space-y-5 pr-1">

                    {/* Add Users Autocomplete */}
                    <div className="space-y-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t('share.add_users')}
                        </label>
                        <div className="flex gap-2 relative">
                            <div className="flex-1 relative">
                                <input
                                    ref={inputRef}
                                    type="text"
                                    value={userInput}
                                    onChange={(e) => {
                                        setUserInput(e.target.value);
                                        setShowSuggestions(true);
                                    }}
                                    onFocus={() => setShowSuggestions(true)}
                                    placeholder={t('share.user_placeholder')}
                                    className="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-800 border border-gray-300 dark:border-zinc-700 text-gray-900 dark:text-white text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 dark:placeholder-gray-400"
                                />

                                {/* Autocomplete Suggestions Dropdown */}
                                {showSuggestions && userInput.trim() && filteredUsers.length > 0 && (
                                    <div
                                        ref={suggestionsRef}
                                        className="absolute left-0 right-0 mt-1 max-h-40 overflow-y-auto bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 rounded-lg shadow-lg z-50 divide-y divide-gray-100 dark:divide-zinc-700"
                                    >
                                        {filteredUsers.map((user, idx) => (
                                            <button
                                                key={idx}
                                                type="button"
                                                onClick={() => {
                                                    setUserInput(user);
                                                    setShowSuggestions(false);
                                                }}
                                                className="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-indigo-50 dark:hover:bg-zinc-700/50 flex items-center gap-2"
                                            >
                                                <User className="w-4 h-4 text-gray-400" />
                                                {user}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Can Edit Checkbox */}
                            <button
                                type="button"
                                onClick={() => setCanEdit(!canEdit)}
                                className="px-3 py-2 text-sm border border-gray-300 dark:border-zinc-700 rounded-lg bg-gray-50 dark:bg-zinc-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-zinc-700 transition-colors flex items-center gap-2 focus:outline-none"
                            >
                                {canEdit ? <CheckSquare className="w-4 h-4 text-indigo-500" /> : <Square className="w-4 h-4 text-gray-400 dark:text-zinc-500" />}
                                <span className="hidden sm:inline">{t('share.can_edit')}</span>
                            </button>

                            {/* Add Button */}
                            <button
                                type="button"
                                onClick={() => handleAddUser(userInput)}
                                disabled={!userInput.trim()}
                                className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg text-sm transition-colors disabled:opacity-50 flex items-center gap-1.5"
                            >
                                <UserPlus className="w-4 h-4" />
                                <span>{t('share.add_btn')}</span>
                            </button>
                        </div>
                    </div>

                    {/* Shared Users List */}
                    <div className="space-y-2">
                        {sharingPermissions.length === 0 ? (
                            <p className="text-xs text-gray-500 dark:text-gray-400 italic bg-gray-50 dark:bg-zinc-800/40 p-3 rounded-lg border border-dashed border-gray-200 dark:border-zinc-800">
                                {t('share.no_users')}
                            </p>
                        ) : (
                            <div className="space-y-2">
                                <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    {t('share.specified_users')}
                                </label>
                                <div className="max-h-36 overflow-y-auto bg-gray-50 dark:bg-zinc-800/30 rounded-lg border border-gray-200 dark:border-zinc-800 divide-y divide-gray-150 dark:divide-zinc-800">
                                    {sharingPermissions.map((user, idx) => (
                                        <div key={idx} className="flex items-center justify-between p-2.5">
                                            <div className="flex items-center gap-2 truncate">
                                                <User className="w-4 h-4 text-gray-400 shrink-0" />
                                                <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{user.username}</span>
                                            </div>
                                            <div className="flex items-center gap-3 shrink-0">
                                                <button
                                                    type="button"
                                                    onClick={() => handleToggleEdit(user.username)}
                                                    className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200 focus:outline-none font-medium"
                                                >
                                                    {user.can_edit ? (
                                                        <CheckSquare className="w-4 h-4 text-indigo-500" />
                                                    ) : (
                                                        <Square className="w-4 h-4 text-gray-400 dark:text-zinc-500" />
                                                    )}
                                                    <span>{t('share.can_edit')}</span>
                                                </button>
                                                <button
                                                    onClick={() => handleRemoveUser(user.username)}
                                                    className="text-red-500 hover:text-red-700 dark:hover:text-red-400 p-1 rounded transition-colors"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Expiration Settings */}
                    <div className="p-4 bg-gray-50 dark:bg-zinc-800/50 rounded-xl border border-gray-150 dark:border-zinc-800 space-y-4">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2">
                                <Calendar className="w-4 h-4 text-gray-450" />
                                {t('share.expire_date')}
                            </span>
                            <button
                                type="button"
                                onClick={() => setIsTimeless(!isTimeless)}
                                className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer select-none font-medium hover:text-gray-800 dark:hover:text-gray-200 focus:outline-none"
                            >
                                {isTimeless ? (
                                    <CheckSquare className="w-5 h-5 text-indigo-500" />
                                ) : (
                                    <Square className="w-5 h-5 text-gray-400 dark:text-zinc-500" />
                                )}
                                <span>{t('share.timeless')}</span>
                            </button>
                        </div>

                        {!isTimeless && (
                            <div className="space-y-1.5 w-full">
                                <div className="flex gap-2">
                                    <input
                                        type="date"
                                        lang={navigator.language}
                                        min={todayStr}
                                        value={expireDate}
                                        onChange={(e) => setExpireDate(e.target.value)}
                                        className="flex-1 px-3 py-2 bg-gray-50 dark:bg-zinc-800 border border-gray-300 dark:border-zinc-700 text-gray-900 dark:text-white text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none"
                                    />
                                    <input
                                        type="time"
                                        value={expireTime}
                                        onChange={(e) => setExpireTime(e.target.value)}
                                        className="w-32 px-3 py-2 bg-gray-50 dark:bg-zinc-800 border border-gray-300 dark:border-zinc-700 text-gray-900 dark:text-white text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none"
                                    />
                                </div>
                                {expireDate && (
                                    <p className="text-xs text-indigo-600 dark:text-indigo-400 font-medium pl-1">
                                        {new Intl.DateTimeFormat(navigator.language, {
                                            dateStyle: 'medium',
                                            timeStyle: 'short'
                                        }).format(new Date(`${expireDate}T${expireTime || '00:00'}`))}
                                    </p>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Link Output Block */}
                    {token && (
                        <div className="space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                                <Link2 className="w-4 h-4 text-indigo-500" />
                                {t('share.link_label')}
                            </label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    readOnly
                                    value={getShareableLink(token)}
                                    className="flex-1 px-3 py-2 bg-gray-100 dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700 text-gray-600 dark:text-zinc-300 text-sm rounded-lg focus:outline-none"
                                />
                                <button
                                    type="button"
                                    onClick={handleCopyLink}
                                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors flex items-center gap-1.5"
                                >
                                    {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                                    <span>{copied ? t('share.copied') : t('share.copy_btn')}</span>
                                </button>
                            </div>
                        </div>
                    )}

                    {error && (
                        <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm border border-red-100 dark:border-red-900/30">
                            {error}
                        </div>
                    )}

                </div>

                {/* Footer Actions */}
                <div className="pt-4 border-t border-gray-200 dark:border-zinc-800 flex justify-between shrink-0">
                    {/* Left side: Revoke button (shown when editing existing share OR after generating a new link) */}
                    <div>
                        {(isEditing || token) && (
                            <button
                                type="button"
                                onClick={handleRevoke}
                                disabled={revoking}
                                className="px-4 py-2 text-sm font-medium text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 dark:bg-red-900/20 dark:border-red-900/30 dark:text-red-400 dark:hover:bg-red-900/40 transition-colors disabled:opacity-50 flex items-center gap-2"
                            >
                                {revoking ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-red-300 border-t-red-600 rounded-full animate-spin" />
                                        {t('share.revoking')}
                                    </>
                                ) : (
                                    <>
                                        <ShieldOff className="w-4 h-4" />
                                        {t('share.revoke_btn')}
                                    </>
                                )}
                            </button>
                        )}
                    </div>

                    {/* Right side: Close + Submit */}
                    <div className="flex gap-3">
                        {!token && (
                            <button
                                type="button"
                                onClick={handleGenerateLink}
                                disabled={loading || (!isTimeless && !expireDate)}
                                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                            >
                                {loading ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        {t('share.generating')}
                                    </>
                                ) : (
                                    isEditing ? t('share.update_btn') : t('share.generate_btn')
                                )}
                            </button>
                        )}
                    </div>
                </div>

            </div>
        </div>
    );
}
