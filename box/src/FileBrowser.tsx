import { useState, useEffect, useMemo, useRef } from 'react';
import { browseFs, mkdirFs, type FSBrowse, type FileInfo, ApiError } from './utils/api';
import { formatBytes, formatDate } from './utils/formats'
import {
    Folder, Image, Film, Music, FileText,
    FileArchive, Binary, FileOutput, FileQuestion,
    ChevronRight, ArrowUp, ArrowDown, ShieldAlert,
    FolderPlus, Upload, Edit2, Download, Trash2
} from 'lucide-react';

const humanReadableType = (type: FileInfo['type']): string => {
    switch (type) {
        case 'dir': return 'Folder';
        case 'image': return 'Image';
        case 'video': return 'Video';
        case 'audio': return 'Audio';
        case 'text': return 'Text Document';
        case 'zip': return 'Archive';
        case 'bin': return 'Binary';
        case 'pdf': return 'PDF Document';
        case 'unk':
        default: return 'Unknown';
    }
};



const FileIcon = ({ type }: { type: FileInfo['type'] }) => {
    const className = "w-5 h-5 text-gray-500 dark:text-gray-400";
    switch (type) {
        case 'dir': return <Folder className="w-5 h-5 text-blue-500 fill-blue-500/20" />;
        case 'image': return <Image className={className} />;
        case 'video': return <Film className={className} />;
        case 'audio': return <Music className={className} />;
        case 'text': return <FileText className={className} />;
        case 'zip': return <FileArchive className={className} />;
        case 'bin': return <Binary className={className} />;
        case 'pdf': return <FileOutput className={className} />;
        case 'unk':
        default: return <FileQuestion className={className} />;
    }
};

export interface FileBrowserProps {
    onAuthError?: (code?: string) => void;
}

export default function FileBrowser({ onAuthError }: FileBrowserProps) {
    const [currentPath, setCurrentPath] = useState<string>('');
    const [browseData, setBrowseData] = useState<FSBrowse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [accessRestricted, setAccessRestricted] = useState(false);
    const [attemptedPath, setAttemptedPath] = useState<string>('');
    const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());

    // Create Folder Modal State
    const [isCreateFolderModalOpen, setIsCreateFolderModalOpen] = useState(false);
    const [newFolderName, setNewFolderName] = useState('');
    const [isCreatingFolder, setIsCreatingFolder] = useState(false);
    const folderInputRef = useRef<HTMLInputElement>(null);

    type SortField = 'name' | 'size' | 'type' | 'date';
    type SortDirection = 'asc' | 'desc';
    const [sortField, setSortField] = useState<SortField>('type');
    const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

    const handleSort = (field: SortField) => {
        if (sortField === field) {
            setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortDirection('asc');
        }
    };

    const sortedFiles = useMemo(() => {
        if (!browseData) return [];
        return [...browseData.files].sort((a, b) => {
            let diff = 0;
            if (sortField === 'name') {
                diff = a.name.localeCompare(b.name);
            } else if (sortField === 'size') {
                diff = (a.size ?? 0) - (b.size ?? 0);
            } else if (sortField === 'type') {
                const typeA = humanReadableType(a.type);
                const typeB = humanReadableType(b.type);
                diff = typeA.localeCompare(typeB);
                if (diff === 0) {
                    diff = a.name.localeCompare(b.name);
                }
            } else if (sortField === 'date') {
                diff = a.creation_time - b.creation_time;
            }
            return sortDirection === 'asc' ? diff : -diff;
        });
    }, [browseData, sortField, sortDirection]);

    const loadPath = async (path: string) => {
        setLoading(true);
        setError(null);
        setAccessRestricted(false);
        setAttemptedPath(path);
        setSelectedItems(new Set());
        try {
            const data = await browseFs(path);
            setBrowseData(data);
            setCurrentPath(path);
        } catch (err) {
            if (err instanceof ApiError) {
                if (err.status === 401) {
                    setAccessRestricted(true);
                    return;
                }
                if (err.status === 403) {
                    if (onAuthError) {
                        onAuthError(err.code);
                        return;
                    }
                }
            }
            setError(err instanceof Error ? err.message : 'Error loading files');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadPath('');
    }, []);

    // Focus input when modal opens
    useEffect(() => {
        if (isCreateFolderModalOpen && folderInputRef.current) {
            folderInputRef.current.focus();
        }
    }, [isCreateFolderModalOpen]);

    const handleCreateFolder = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newFolderName.trim()) return;

        setIsCreatingFolder(true);
        setError(null);
        try {
            await mkdirFs(currentPath, newFolderName.trim());
            setIsCreateFolderModalOpen(false);
            setNewFolderName('');
            await loadPath(currentPath); // Refresh current path
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error creating folder');
            setIsCreateFolderModalOpen(false); // Close on error as well and show it in main view
        } finally {
            setIsCreatingFolder(false);
        }
    };

    const handleRowClick = (e: React.MouseEvent, file: FileInfo) => {
        if (e.ctrlKey || e.metaKey) {
            setSelectedItems(prev => {
                const newSet = new Set(prev);
                if (newSet.has(file.name)) {
                    newSet.delete(file.name);
                } else {
                    newSet.add(file.name);
                }
                return newSet;
            });
        } else {
            setSelectedItems(prev => {
                if (prev.has(file.name) && prev.size === 1) {
                    return new Set();
                }
                return new Set([file.name]);
            });
        }
    };

    const handleDoubleClick = (file: FileInfo) => {
        if (file.type === 'dir') {
            const nextPath = currentPath ? `${currentPath}/${file.name}` : file.name;
            loadPath(nextPath);
        }
    };

    const handleBreadcrumbClick = (index: number, parts: string[]) => {
        // If clicking "Your files" (index 0), go to root
        if (index === 0) {
            loadPath('');
            return;
        }
        // Reconstruct path up to the clicked part
        const targetParts = parts.slice(1, index + 1); // skip '.'
        const nextPath = targetParts.join('/');
        loadPath(nextPath);
    };

    const renderBreadcrumbs = () => {
        if (!browseData) return null;

        // path might be "." or "foo/bar" or "./foo/bar"
        let pathString = browseData.path;
        if (pathString.startsWith('./')) {
            pathString = pathString.substring(2);
        }

        // Construct parts array starting with root
        const parts = ['.'];
        if (pathString && pathString !== '.') {
            parts.push(...pathString.split('/').filter(Boolean));
        }

        return (
            <div className="flex flex-wrap items-center gap-1 text-sm font-medium text-gray-600 dark:text-gray-300 mb-6">
                {parts.map((part, index) => {
                    const isLast = index === parts.length - 1;
                    const label = part === '.' ? 'Your files' : part;

                    return (
                        <div key={index} className="flex items-center gap-1">
                            <button
                                onClick={() => handleBreadcrumbClick(index, parts)}
                                disabled={isLast}
                                className={`hover:text-indigo-600 dark:hover:text-indigo-400 focus:outline-none transition-colors ${isLast ? 'text-gray-900 dark:text-gray-100 cursor-default' : 'cursor-pointer'
                                    }`}
                            >
                                {label}
                            </button>
                            {!isLast && <ChevronRight className="w-4 h-4 text-gray-400" />}
                        </div>
                    );
                })}
            </div>
        );
    };

    const renderActions = () => {
        const multiSelected = selectedItems.size > 1;
        const noneSelected = selectedItems.size === 0;
        const singleSelected = selectedItems.size === 1;

        return (
            <div className="flex flex-wrap items-center gap-3 mb-6 pb-6 border-b border-gray-200 dark:border-zinc-800">
                <button
                    onClick={() => setIsCreateFolderModalOpen(true)}
                    disabled={multiSelected}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                >
                    <FolderPlus className="w-4 h-4" />
                    Create Folder
                </button>
                <button
                    disabled={multiSelected}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                >
                    <Upload className="w-4 h-4" />
                    Upload file
                </button>
                <button
                    disabled={!singleSelected}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                >
                    <Edit2 className="w-4 h-4" />
                    Rename
                </button>
                <button
                    disabled={noneSelected}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                >
                    <Download className="w-4 h-4" />
                    Download
                </button>
                <button
                    disabled={noneSelected}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-red-900/30 dark:text-red-400 dark:hover:bg-red-900/20 transition-colors"
                >
                    <Trash2 className="w-4 h-4" />
                    Delete
                </button>
            </div>
        );
    };

    const SortHeader = ({ field, label, align = 'left' }: { field: SortField, label: string, align?: 'left' | 'right' }) => (
        <th
            className={`pb-3 font-medium px-4 cursor-pointer hover:text-gray-900 dark:hover:text-gray-100 select-none ${align === 'right' ? 'text-right' : 'text-left'}`}
            onClick={() => handleSort(field)}
        >
            <div className={`flex items-center gap-1 inline-flex ${align === 'right' ? 'flex-row-reverse' : ''}`}>
                {label}
                {sortField === field ? (
                    sortDirection === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />
                ) : (
                    <div className="w-3 h-3" />
                )}
            </div>
        </th>
    );

    if (accessRestricted) {
        return (
            <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 p-12 min-h-[500px] flex flex-col items-center justify-center text-center">
                <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-6">
                    <ShieldAlert className="w-8 h-8 text-red-600 dark:text-red-400" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Access Restricted</h2>
                <p className="text-gray-500 dark:text-gray-400 mb-8 max-w-md">
                    You do not have permission to view the contents of this directory.
                </p>
                <button
                    onClick={() => {
                        loadPath(currentPath === attemptedPath ? '' : currentPath);
                    }}
                    className="px-6 py-2.5 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 transition-colors"
                >
                    Go Back
                </button>
            </div>
        );
    }

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 p-6 md:p-8 min-h-[500px]">
            {isCreateFolderModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 dark:bg-black/50 backdrop-blur-sm">
                    <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl ring-1 ring-gray-900/5 dark:ring-white/10 w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                                <FolderPlus className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Create New Folder</h3>
                        </div>
                        <form onSubmit={handleCreateFolder}>
                            <div className="mb-6">
                                <label htmlFor="folderName" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Folder Name
                                </label>
                                <input
                                    ref={folderInputRef}
                                    type="text"
                                    id="folderName"
                                    value={newFolderName}
                                    onChange={(e) => setNewFolderName(e.target.value)}
                                    placeholder="e.g. New Project"
                                    className="w-full px-4 py-2 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block dark:bg-zinc-800 dark:border-zinc-700 dark:placeholder-gray-400 dark:text-white dark:focus:ring-indigo-500 dark:focus:border-indigo-500"
                                    disabled={isCreatingFolder}
                                    autoFocus
                                />
                            </div>
                            <div className="flex justify-end gap-3">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setIsCreateFolderModalOpen(false);
                                        setNewFolderName('');
                                    }}
                                    disabled={isCreatingFolder}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-300 dark:hover:bg-zinc-700 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isCreatingFolder || !newFolderName.trim()}
                                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 dark:focus:ring-offset-zinc-900 transition-colors flex items-center gap-2"
                                >
                                    {isCreatingFolder ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                            Creating...
                                        </>
                                    ) : (
                                        'Create'
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {renderActions()}
            {renderBreadcrumbs()}

            {error && (
                <div className="p-4 mb-6 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm border border-red-100 dark:border-red-900/30">
                    {error}
                </div>
            )}

            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm whitespace-nowrap">
                    <thead className="text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-zinc-800">
                        <tr>
                            <SortHeader field="name" label="Name" />
                            <SortHeader field="size" label="Size" align="right" />
                            <SortHeader field="type" label="Type" />
                            <SortHeader field="date" label="Date Modified" align="right" />
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-zinc-800">
                        {loading && !browseData ? (
                            <tr>
                                <td colSpan={4} className="py-8 text-center text-gray-500">
                                    Loading...
                                </td>
                            </tr>
                        ) : browseData?.files.length === 0 ? (
                            <tr>
                                <td colSpan={4} className="py-8 text-center text-gray-500">
                                    This folder is empty.
                                </td>
                            </tr>
                        ) : (
                            sortedFiles.map((file, idx) => (
                                <tr
                                    key={idx}
                                    onClick={(e) => handleRowClick(e, file)}
                                    onDoubleClick={() => handleDoubleClick(file)}
                                    className={`group transition-colors cursor-pointer ${selectedItems.has(file.name)
                                        ? 'bg-indigo-50 dark:bg-indigo-900/20'
                                        : 'hover:bg-gray-50 dark:hover:bg-zinc-800/50'
                                        }`}
                                >
                                    <td className="py-3 px-4">
                                        <div className="flex items-center gap-3">
                                            <FileIcon type={file.type} />
                                            <span className={`font-medium ${file.type === 'dir' ? 'text-gray-900 dark:text-gray-100' : 'text-gray-700 dark:text-gray-300'}`}>
                                                {file.name}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="py-3 px-4 text-right text-gray-500 dark:text-gray-400 tabular-nums">
                                        {file.type !== 'dir' ? formatBytes(file.size) : '--'}
                                    </td>
                                    <td className="py-3 px-4 text-left text-gray-500 dark:text-gray-400">
                                        {humanReadableType(file.type)}
                                    </td>
                                    <td className="py-3 px-4 text-right text-gray-500 dark:text-gray-400 tabular-nums">
                                        {formatDate(file.creation_time)}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
