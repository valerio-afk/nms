import { useState, useEffect, useMemo, useRef, useContext } from 'react';
import { browseFs, mkdirFs, mvFs, rmFs, zipFs, unzipFs, type FSBrowse, type FileInfo, ApiError, API_BASE_URL } from './utils/api';
import Uppy from '@uppy/core';
import Tus from '@uppy/tus';
import DashboardModal from '@uppy/react/dashboard-modal';
import '@uppy/core/css/style.min.css';
import '@uppy/dashboard/css/style.min.css';
import { formatBytes, formatDate } from './utils/formats'
import {
    Folder, Image, Film, Music, FileText,
    FileArchive, Binary, FileOutput, FileQuestion,
    ChevronRight, ArrowUp, ArrowDown, ShieldAlert,
    FolderPlus, Upload, Edit2, Download, Trash2,
    MoveRight, CornerLeftUp, ArchiveRestore
} from 'lucide-react';
import { ContextMenuContext } from './App';
import FilePreviewModal from './components/FilePreviewModal';

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
    const { ctxMenuPosition, setCtxMenuPosition, handleContextMenuClick } = useContext(ContextMenuContext);
    const [currentPath, setCurrentPath] = useState<string>('');
    const [browseData, setBrowseData] = useState<FSBrowse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [accessRestricted, setAccessRestricted] = useState(false);
    const [attemptedPath, setAttemptedPath] = useState<string>('');
    const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
    const [lastSelectedAnchor, setLastSelectedAnchor] = useState<string | null>(null);

    // Create Folder Modal State
    const [isCreateFolderModalOpen, setIsCreateFolderModalOpen] = useState(false);
    const [newFolderName, setNewFolderName] = useState('');
    const [isCreatingFolder, setIsCreatingFolder] = useState(false);
    const folderInputRef = useRef<HTMLInputElement>(null);

    // Rename Modal State
    const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
    const [newFileName, setNewFileName] = useState('');
    const [isRenaming, setIsRenaming] = useState(false);
    const [itemToRename, setItemToRename] = useState<string | null>(null);
    const renameInputRef = useRef<HTMLInputElement>(null);

    // Delete Modal State
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    // Zip Context State
    const [isZipModalOpen, setIsZipModalOpen] = useState(false);
    const [zipFileName, setZipFileName] = useState('');
    const [isZipping, setIsZipping] = useState(false);
    const [isUnzipping, setIsUnzipping] = useState(false);

    // Move Modal (Directory Picker) State
    const [isMoveModalOpen, setIsMoveModalOpen] = useState(false);
    const [isMoving, setIsMoving] = useState(false);
    const [pickerPath, setPickerPath] = useState('');
    const [pickerData, setPickerData] = useState<FSBrowse | null>(null);
    const [pickerLoading, setPickerLoading] = useState(false);

    // Drag and Drop State
    const [draggedItem, setDraggedItem] = useState<string | null>(null);

    // File Preview Modal State
    const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
    const [previewFile, setPreviewFile] = useState<FileInfo | null>(null);

    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const [isDraggingOverMain, setIsDraggingOverMain] = useState(false);
    const [dragOverFolder, setDragOverFolder] = useState<string | null>(null);
    const [isDarkMode, setIsDarkMode] = useState(() => document.documentElement.classList.contains('dark'));

    const [currentConflict, setCurrentConflict] = useState<{
        file: import('@uppy/core').UppyFile<any, any>;
        resolve: (action: { type: 'resume' | 'overwrite' | 'rename', newName?: string }) => void;
    } | null>(null);
    const [conflictNewName, setConflictNewName] = useState('');

    useEffect(() => {
        const uppyRoot = document.querySelector('.uppy-Root');
        if (uppyRoot) {
            if (currentConflict) {
                uppyRoot.setAttribute('inert', 'true');
            } else {
                uppyRoot.removeAttribute('inert');
            }
        }
    }, [currentConflict]);

    const browseDataRef = useRef(browseData);
    useEffect(() => {
        browseDataRef.current = browseData;
    }, [browseData]);

    useEffect(() => {
        const observer = new MutationObserver(() => {
            setIsDarkMode(document.documentElement.classList.contains('dark'));
        });
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
        return () => observer.disconnect();
    }, []);

    const currentPathRef = useRef(currentPath);
    useEffect(() => {
        currentPathRef.current = currentPath;
    }, [currentPath]);

    const uppy = useMemo(() => {
        const token = localStorage.getItem('authToken') || '';
        const u = new Uppy({
            allowMultipleUploadBatches: true,
        }).use(Tus, {
            endpoint: `${API_BASE_URL}/fs/upload`,
            headers: token ? { Authorization: `Bearer ${token}` } : {},
            chunkSize: 10 * 1024 * 1024, // 10MB chunk size
        });

        u.on('file-added', (file) => {
            const fileState = u.getFile(file.id);
            if (!fileState) return;
            const newMeta = { ...fileState.meta };
            delete newMeta.filename;
            delete newMeta.relativePath;

            let resolvedPath = newMeta.path !== undefined ? String(newMeta.path) : currentPathRef.current;
            if (!resolvedPath || resolvedPath === "/") {
                resolvedPath = "./";
            } else if (resolvedPath !== "." && !resolvedPath.startsWith("./")) {
                resolvedPath = `./${resolvedPath}`;
            }
            newMeta.path = resolvedPath;

            u.setFileState(file.id, { meta: newMeta });
        });

        u.addPreProcessor(async (fileIDs) => {
            for (const fileID of fileIDs) {
                const file = u.getFile(fileID);
                if (!file) continue;

                const uploadPath = file.meta.path as string;
                const fileName = file.name;

                const normalizedUploadPath = uploadPath === './' ? '' : uploadPath.replace(/^\.\//, '');

                let fileExists = false;
                if (normalizedUploadPath === currentPathRef.current && browseDataRef.current) {
                    fileExists = browseDataRef.current.files.some(f => f.name === fileName);
                } else {
                    try {
                        const data = await browseFs(normalizedUploadPath);
                        fileExists = data.files.some(f => f.name === fileName);
                    } catch (e) {
                        // Directory access issue or it doesn't exist, ignore
                    }
                }

                if (fileExists) {
                    const action = await new Promise<{ type: 'resume' | 'overwrite' | 'rename', newName?: string }>((resolve) => {
                        setCurrentConflict({
                            file,
                            resolve: (actionType) => resolve(actionType)
                        });
                    });

                    setCurrentConflict(null);
                    setConflictNewName('');

                    if (action.type === 'overwrite') {
                        const targetDelPath = normalizedUploadPath ? `${normalizedUploadPath}/${fileName}` : fileName;
                        try {
                            await rmFs(targetDelPath);
                        } catch (e) {
                            console.error('Failed to overwrite', e);
                        }
                    } else if (action.type === 'rename' && action.newName) {
                        const fileState = u.getFile(fileID);
                        u.setFileState(fileID, {
                            name: action.newName,
                            meta: { ...fileState.meta, name: action.newName }
                        });
                    }
                }
            }
        });

        return u;
    }, []);

    useEffect(() => {
        const handleComplete = () => {
            loadPath(currentPathRef.current);
            setIsUploadModalOpen(false);
        };
        uppy.on('complete', handleComplete);
        return () => {
            uppy.off('complete', handleComplete);
        };
    }, [uppy]);

    useEffect(() => {
        if (!isUploadModalOpen) {
            uppy.cancelAll();
        }
    }, [isUploadModalOpen, uppy]);

    type SortField = 'name' | 'size' | 'type' | 'date';
    type SortDirection = 'asc' | 'desc';
    const [sortField, setSortField] = useState<SortField>('type');
    const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

    const handleContextMenu = (event: React.MouseEvent) => {
        event.preventDefault(); // prevent default browser menu
        setCtxMenuPosition({ x: event.pageX, y: event.pageY });
    };



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
        setLastSelectedAnchor(null);
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

    const loadPickerPath = async (path: string) => {
        setPickerLoading(true);
        try {
            const data = await browseFs(path);
            // Only keep directories and sort them alphabetically
            const directoriesOnly = data.files
                .filter(f => f.type === 'dir')
                .sort((a, b) => a.name.localeCompare(b.name));
            setPickerData({ ...data, files: directoriesOnly });
            setPickerPath(path);
        } catch (err) {
            // Silently fail or log error in picker
            console.error(err);
        } finally {
            setPickerLoading(false);
        }
    };

    useEffect(() => {
        loadPath('');
    }, []);

    // Load picker root when modal opens
    useEffect(() => {
        if (isMoveModalOpen) {
            loadPickerPath(currentPath);
        }
    }, [isMoveModalOpen, currentPath]);

    // Focus input when modal opens
    useEffect(() => {
        if (isCreateFolderModalOpen && folderInputRef.current) {
            folderInputRef.current.focus();
        }
    }, [isCreateFolderModalOpen]);

    // Focus input when rename modal opens
    useEffect(() => {
        if (isRenameModalOpen && renameInputRef.current) {
            renameInputRef.current.focus();
        }
    }, [isRenameModalOpen]);

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

    const handleRename = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newFileName.trim() || !itemToRename || newFileName.trim() === itemToRename) return;

        setIsRenaming(true);
        setError(null);
        try {
            const oldPath = currentPath ? `${currentPath}/${itemToRename}` : itemToRename;
            const newPath = currentPath ? `${currentPath}/${newFileName.trim()}` : newFileName.trim();
            await mvFs(oldPath, newPath);
            setIsRenameModalOpen(false);
            setNewFileName('');
            setItemToRename(null);
            setSelectedItems(new Set());
            await loadPath(currentPath);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error renaming file');
            setIsRenameModalOpen(false);
        } finally {
            setIsRenaming(false);
        }
    };

    const handleDelete = async () => {
        if (selectedItems.size === 0) return;

        setIsDeleting(true);
        setError(null);
        try {
            const itemsToDelete = Array.from(selectedItems);
            await Promise.all(itemsToDelete.map(item => {
                const itemPath = currentPath ? `${currentPath}/${item}` : item;
                return rmFs(itemPath);
            }));

            setIsDeleteModalOpen(false);
            setSelectedItems(new Set());
            setLastSelectedAnchor(null);
            await loadPath(currentPath);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error deleting files');
            // Reload the view anyway in case some items were deleted successfully
            await loadPath(currentPath);
            setIsDeleteModalOpen(false);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleZipSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!zipFileName.trim() || selectedItems.size === 0) return;

        setIsZipping(true);
        setError(null);
        try {
            let finalZipName = zipFileName.trim();
            if (!finalZipName.toLowerCase().endsWith('.zip')) {
                finalZipName += '.zip';
            }
            const targetPath = currentPath ? `${currentPath}/${finalZipName}` : finalZipName;
            
            // Relative paths from user root requested by backend
            const itemsToZip = Array.from(selectedItems).map(item => currentPath ? `${currentPath}/${item}` : item);
            
            await zipFs(targetPath, itemsToZip);
            setIsZipModalOpen(false);
            setZipFileName('');
            setSelectedItems(new Set());
            await loadPath(currentPath);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error zipping files');
            setIsZipModalOpen(false);
        } finally {
            setIsZipping(false);
        }
    };

    const handleUnzip = async () => {
        if (selectedItems.size !== 1) return;
        const item = Array.from(selectedItems)[0];
        const itemPath = currentPath ? `${currentPath}/${item}` : item;
        
        setIsUnzipping(true);
        setError(null);
        try {
            await unzipFs(itemPath);
            setSelectedItems(new Set());
            await loadPath(currentPath);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error unzipping archive');
        } finally {
            setIsUnzipping(false);
        }
    };

    const handleMoveSubmit = async () => {
        if (selectedItems.size === 0) return;

        setIsMoving(true);
        setError(null);
        try {
            const itemsToMove = Array.from(selectedItems);

            await Promise.all(itemsToMove.map(item => {
                const oldPath = currentPath ? `${currentPath}/${item}` : item;
                const newPath = pickerPath ? `${pickerPath}/${item}` : item;

                // Need to avoid moving to same directory
                if (oldPath === newPath) return Promise.resolve();

                return mvFs(oldPath, newPath);
            }));

            setIsMoveModalOpen(false);
            setSelectedItems(new Set());
            setLastSelectedAnchor(null);
            await loadPath(currentPath);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error moving files');
            await loadPath(currentPath); // Reload in case some moved successfully
            setIsMoveModalOpen(false);
        } finally {
            setIsMoving(false);
        }
    };

    const openRenameModal = () => {
        if (selectedItems.size !== 1) return;
        const item = Array.from(selectedItems)[0];
        setItemToRename(item);
        setNewFileName(item);
        setIsRenameModalOpen(true);
    };

    const handleDragStart = (e: React.DragEvent, fileName: string) => {
        setDraggedItem(fileName);
        let itemsToDrag = Array.from(selectedItems.has(fileName) ? selectedItems : [fileName]);
        if (!selectedItems.has(fileName)) {
            setSelectedItems(new Set([fileName]));
            setLastSelectedAnchor(fileName);
        }
        e.dataTransfer.setData('text/plain', JSON.stringify(itemsToDrag));
    };

    const handleMainDragEnter = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
            setIsDraggingOverMain(true);
        }
    };

    const handleMainDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        const rect = e.currentTarget.getBoundingClientRect();
        if (
            e.clientX <= rect.left || e.clientX >= rect.right ||
            e.clientY <= rect.top || e.clientY >= rect.bottom ||
            e.clientY === 0
        ) {
            setIsDraggingOverMain(false);
        }
    };

    const handleMainDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        if (e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
            e.dataTransfer.dropEffect = 'copy';
        }
    };

    const handleMainDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDraggingOverMain(false);
        setDragOverFolder(null);
        if (e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {

            Array.from(e.dataTransfer.files).forEach(file => {
                uppy.addFile({
                    name: file.name,
                    type: file.type,
                    data: file,
                    meta: {
                        path: currentPath || "./"
                    }
                });
            });
            setIsUploadModalOpen(true);
        }
    };

    const handleFolderDragEnter = (e: React.DragEvent, targetName: string) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
            setDragOverFolder(targetName);
        }
    };

    const handleFolderDragLeave = (e: React.DragEvent, targetName: string) => {
        e.preventDefault();
        e.stopPropagation();
        const rect = e.currentTarget.getBoundingClientRect();
        if (
            e.clientX <= rect.left || e.clientX >= rect.right ||
            e.clientY <= rect.top || e.clientY >= rect.bottom ||
            e.clientY === 0
        ) {
            if (dragOverFolder === targetName) setDragOverFolder(null);
        }
    };

    const handleDragOver = (e: React.DragEvent, targetName?: string) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
            e.dataTransfer.dropEffect = 'copy';
            if (targetName && dragOverFolder !== targetName) {
                setDragOverFolder(targetName);
            }
        } else {
            e.dataTransfer.dropEffect = 'move';
        }
    };

    const handleDrop = async (e: React.DragEvent, targetFile: FileInfo) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDraggingOverMain(false);
        setDragOverFolder(null);

        if (e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
            const targetPath = targetFile.type === 'dir'
                ? (currentPath ? `${currentPath}/${targetFile.name}` : targetFile.name)
                : currentPath;

            Array.from(e.dataTransfer.files).forEach(file => {
                uppy.addFile({
                    name: file.name,
                    type: file.type,
                    data: file,
                    meta: {
                        path: targetPath || "./"
                    }
                });
            });
            setIsUploadModalOpen(true);
            return;
        }

        if (!draggedItem) {
            return;
        }

        if (targetFile.type !== 'dir') {
            setDraggedItem(null);
            return;
        }

        const itemsToMove = selectedItems.has(draggedItem) ? Array.from(selectedItems) : [draggedItem];

        if (itemsToMove.includes(targetFile.name)) {
            setDraggedItem(null);
            return;
        }

        setError(null);
        try {
            await Promise.all(itemsToMove.map(item => {
                const oldPath = currentPath ? `${currentPath}/${item}` : item;
                const newPath = currentPath ? `${currentPath}/${targetFile.name}/${item}` : `${targetFile.name}/${item}`;
                return mvFs(oldPath, newPath);
            }));
            setSelectedItems(new Set());
            setLastSelectedAnchor(null);
            await loadPath(currentPath);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Error moving files');
            await loadPath(currentPath); // Reload in case some moved successfully
        } finally {
            setDraggedItem(null);
        }
    };

    const handleRowClick = (e: React.MouseEvent, file: FileInfo, index: number) => {
        if (e.shiftKey && lastSelectedAnchor !== null) {
            const documentSelection = window.getSelection();
            if (documentSelection) {
                documentSelection.removeAllRanges();
            }

            const anchorIndex = sortedFiles.findIndex(f => f.name === lastSelectedAnchor);
            if (anchorIndex !== -1) {
                const start = Math.min(index, anchorIndex);
                const end = Math.max(index, anchorIndex);

                const newSelection = new Set<string>();
                for (let i = start; i <= end; i++) {
                    newSelection.add(sortedFiles[i].name);
                }

                if (e.ctrlKey || e.metaKey) {
                    setSelectedItems(prev => {
                        const newSet = new Set(prev);
                        newSelection.forEach(val => newSet.add(val));
                        return newSet;
                    });
                } else {
                    setSelectedItems(newSelection);
                }
                return;
            }
        }

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
            setLastSelectedAnchor(file.name);
        } else {
            setSelectedItems(prev => {
                if (prev.has(file.name) && prev.size === 1) {
                    setLastSelectedAnchor(null);
                    return new Set();
                }
                setLastSelectedAnchor(file.name);
                return new Set([file.name]);
            });
        }
    };

    const handleDoubleClick = (file: FileInfo) => {
        if (file.type === 'dir') {
            const nextPath = currentPath ? `${currentPath}/${file.name}` : file.name;
            loadPath(nextPath);
        } else {
            setPreviewFile(file);
            setIsPreviewModalOpen(true);
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

    const multiSelected = selectedItems.size > 1;
    const noneSelected = selectedItems.size === 0;
    const singleSelected = selectedItems.size === 1;
    const isSingleZipSelected = singleSelected && Array.from(selectedItems)[0].toLowerCase().endsWith('.zip');

    return (
        <div
            className={`bg-white dark:bg-zinc-900 rounded-2xl shadow-sm ring-1 ring-gray-900/5 p-6 md:p-8 min-h-[500px] transition-colors ${
                isDraggingOverMain && !dragOverFolder
                    ? 'bg-indigo-50/50 dark:bg-indigo-900/10 border-2 border-dashed border-indigo-400 dark:border-indigo-500'
                    : 'dark:ring-white/10'
            }`}
            onContextMenu={handleContextMenu}
            onClick={handleContextMenuClick}
            onDragEnter={handleMainDragEnter}
            onDragLeave={handleMainDragLeave}
            onDragOver={handleMainDragOver}
            onDrop={handleMainDrop}
        >
            <DashboardModal
                uppy={uppy}
                open={isUploadModalOpen}
                onRequestClose={() => setIsUploadModalOpen(false)}
                closeModalOnClickOutside
                proudlyDisplayPoweredByUppy={false}
                theme={isDarkMode ? 'dark' : 'light'}
            />

            {currentConflict && (
                <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-gray-900/50 dark:bg-black/50 backdrop-blur-sm">
                    <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl ring-1 ring-gray-900/5 dark:ring-white/10 w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center">
                                <ShieldAlert className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">File Already Exists</h3>
                        </div>
                        <div className="mb-6">
                            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                A file named <strong className="text-gray-900 dark:text-gray-100 break-all">{currentConflict.file.name}</strong> already exists in this folder.
                            </p>
                            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                                What would you like to do?
                            </p>
                            
                            <div className="space-y-3">
                                <button
                                    onClick={() => currentConflict.resolve({ type: 'resume' })}
                                    className="w-full px-4 py-2 text-sm font-medium text-left text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                                >
                                    <strong>Resume Upload</strong>
                                    <span className="block text-xs font-normal text-gray-500 dark:text-gray-400">Continue the upload (append or resume if supported)</span>
                                </button>
                                <button
                                    onClick={() => currentConflict.resolve({ type: 'overwrite' })}
                                    className="w-full px-4 py-2 text-sm font-medium text-left text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 dark:bg-zinc-800 dark:border-red-900/30 dark:text-red-400 dark:hover:bg-red-900/20 transition-colors"
                                >
                                    <strong>Overwrite File</strong>
                                    <span className="block text-xs font-normal text-red-500/80 dark:text-red-400/80">Delete the existing file and upload this one</span>
                                </button>
                                <div className="p-3 border border-gray-200 dark:border-zinc-700 rounded-lg">
                                    <label htmlFor="conflictRename" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                        Rename New File
                                    </label>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            id="conflictRename"
                                            value={conflictNewName}
                                            onChange={(e) => setConflictNewName(e.target.value)}
                                            placeholder="Enter new filename"
                                            className="flex-1 px-3 py-1.5 text-sm bg-gray-50 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 dark:bg-zinc-800 dark:border-zinc-700 dark:placeholder-gray-400 dark:text-white"
                                        />
                                        <button
                                            onClick={() => currentConflict.resolve({ type: 'rename', newName: conflictNewName })}
                                            disabled={!conflictNewName.trim() || conflictNewName.trim() === currentConflict.file.name}
                                            className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                                        >
                                            Rename
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

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

            {isRenameModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 dark:bg-black/50 backdrop-blur-sm">
                    <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl ring-1 ring-gray-900/5 dark:ring-white/10 w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                                <Edit2 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Rename Item</h3>
                        </div>
                        <form onSubmit={handleRename}>
                            <div className="mb-6">
                                <label htmlFor="fileName" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    New Name
                                </label>
                                <input
                                    ref={renameInputRef}
                                    type="text"
                                    id="fileName"
                                    value={newFileName}
                                    onChange={(e) => setNewFileName(e.target.value)}
                                    className="w-full px-4 py-2 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block dark:bg-zinc-800 dark:border-zinc-700 dark:placeholder-gray-400 dark:text-white dark:focus:ring-indigo-500 dark:focus:border-indigo-500"
                                    disabled={isRenaming}
                                    autoFocus
                                />
                            </div>
                            <div className="flex justify-end gap-3">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setIsRenameModalOpen(false);
                                        setNewFileName('');
                                        setItemToRename(null);
                                    }}
                                    disabled={isRenaming}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-300 dark:hover:bg-zinc-700 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isRenaming || !newFileName.trim() || newFileName.trim() === itemToRename}
                                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 dark:focus:ring-offset-zinc-900 transition-colors flex items-center gap-2"
                                >
                                    {isRenaming ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                            Renaming...
                                        </>
                                    ) : (
                                        'Rename'
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {isDeleteModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 dark:bg-black/50 backdrop-blur-sm">
                    <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl ring-1 ring-gray-900/5 dark:ring-white/10 w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                                <Trash2 className="w-5 h-5 text-red-600 dark:text-red-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Confirm Deletion</h3>
                        </div>

                        <div className="mb-6">
                            <p className="text-sm text-gray-700 dark:text-gray-300 mb-4">
                                Are you sure you want to delete the following item{selectedItems.size > 1 ? 's' : ''}?
                                <strong className="block mt-2 text-red-600 dark:text-red-400">
                                    This action is permanent and there is no way to recover these files.
                                </strong>
                            </p>

                            <div className="max-h-40 overflow-y-auto bg-gray-50 dark:bg-zinc-800 rounded-lg border border-gray-200 dark:border-zinc-700 p-2">
                                <ul className="text-sm text-gray-600 dark:text-gray-400 list-inside list-disc">
                                    {Array.from(selectedItems).map((item, idx) => (
                                        <li key={idx} className="truncate px-2 py-1">{item}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>

                        <div className="flex justify-end gap-3">
                            <button
                                type="button"
                                onClick={() => setIsDeleteModalOpen(false)}
                                disabled={isDeleting}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50 dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-300 dark:hover:bg-zinc-700 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleDelete}
                                disabled={isDeleting}
                                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 dark:focus:ring-offset-zinc-900 transition-colors flex items-center gap-2"
                            >
                                {isDeleting ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        Deleting...
                                    </>
                                ) : (
                                    'Delete'
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isMoveModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 dark:bg-black/50 backdrop-blur-sm">
                    <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl ring-1 ring-gray-900/5 dark:ring-white/10 w-full max-w-lg p-6 animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                                <MoveRight className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Select Destination</h3>
                        </div>

                        <div className="mb-6">
                            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 truncate">
                                Current selection: {pickerPath || '/ (Root)'}
                            </p>

                            <div className="h-64 overflow-y-auto bg-gray-50 dark:bg-zinc-800/50 rounded-lg border border-gray-200 dark:border-zinc-700">
                                {pickerLoading && !pickerData ? (
                                    <div className="flex items-center justify-center h-full text-sm text-gray-500">Loading...</div>
                                ) : (
                                    <ul className="text-sm font-medium">
                                        {/* Parent directory navigation item */}
                                        <li
                                            onClick={() => {
                                                if (!pickerPath) return; // At root
                                                const parts = pickerPath.split('/');
                                                parts.pop();
                                                loadPickerPath(parts.join('/'));
                                            }}
                                            className={`flex items-center gap-2 px-4 py-2 hover:bg-gray-100 dark:hover:bg-zinc-700 cursor-pointer text-gray-600 dark:text-gray-300 ${!pickerPath ? 'opacity-50 cursor-not-allowed hidden' : ''}`}
                                        >
                                            <CornerLeftUp className="w-4 h-4" />
                                            .. (Parent Directory)
                                        </li>

                                        {/* Available directories */}
                                        {pickerData?.files.length === 0 ? (
                                            <li className="px-4 py-4 text-center text-gray-500 dark:text-gray-400">No directories found.</li>
                                        ) : (
                                            pickerData?.files.map((dir, idx) => (
                                                <li
                                                    key={idx}
                                                    onClick={() => {
                                                        const nextPath = pickerPath ? `${pickerPath}/${dir.name}` : dir.name;
                                                        loadPickerPath(nextPath);
                                                    }}
                                                    className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 dark:hover:bg-zinc-700 cursor-pointer text-gray-700 dark:text-gray-200"
                                                >
                                                    <Folder className="w-4 h-4 text-blue-500 fill-blue-500/20" />
                                                    {dir.name}
                                                </li>
                                            ))
                                        )}
                                    </ul>
                                )}
                            </div>
                        </div>

                        <div className="flex justify-end gap-3">
                            <button
                                type="button"
                                onClick={() => setIsMoveModalOpen(false)}
                                disabled={isMoving}
                                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50 dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-300 dark:hover:bg-zinc-700 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleMoveSubmit}
                                disabled={isMoving}
                                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 dark:focus:ring-offset-zinc-900 transition-colors flex items-center gap-2"
                            >
                                {isMoving ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        Moving...
                                    </>
                                ) : (
                                    'Move Here'
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isZipModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 dark:bg-black/50 backdrop-blur-sm">
                    <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl ring-1 ring-gray-900/5 dark:ring-white/10 w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                                <FileArchive className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                            </div>
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Create Archive</h3>
                        </div>
                        <form onSubmit={handleZipSubmit}>
                            <div className="mb-6">
                                <label htmlFor="zipName" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Archive Name
                                </label>
                                <input
                                    type="text"
                                    id="zipName"
                                    value={zipFileName}
                                    onChange={(e) => setZipFileName(e.target.value)}
                                    placeholder="e.g. backup.zip"
                                    className="w-full px-4 py-2 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block dark:bg-zinc-800 dark:border-zinc-700 dark:placeholder-gray-400 dark:text-white dark:focus:ring-indigo-500 dark:focus:border-indigo-500"
                                    disabled={isZipping}
                                    autoFocus
                                />
                            </div>
                            <div className="flex justify-end gap-3">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setIsZipModalOpen(false);
                                        setZipFileName('');
                                    }}
                                    disabled={isZipping}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-300 dark:hover:bg-zinc-700 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isZipping || !zipFileName.trim()}
                                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 dark:focus:ring-offset-zinc-900 transition-colors flex items-center gap-2"
                                >
                                    {isZipping ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                            Zipping...
                                        </>
                                    ) : (
                                        'Zip'
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            <FilePreviewModal
                isOpen={isPreviewModalOpen}
                onClose={() => {
                    setIsPreviewModalOpen(false);
                    setPreviewFile(null);
                }}
                file={previewFile}
                currentPath={currentPath}
            />

            {
                <>
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
                            onClick={() => setIsUploadModalOpen(true)}
                            disabled={multiSelected}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                        >
                            <Upload className="w-4 h-4" />
                            Upload file
                        </button>
                        <button
                            disabled={!singleSelected}
                            onClick={openRenameModal}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                        >
                            <Edit2 className="w-4 h-4" />
                            Rename
                        </button>
                        <button
                            disabled={noneSelected}
                            onClick={() => setIsMoveModalOpen(true)}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                        >
                            <MoveRight className="w-4 h-4" />
                            Move
                        </button>
                        <button
                            disabled={noneSelected}
                            onClick={() => setIsZipModalOpen(true)}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                        >
                            <FileArchive className="w-4 h-4" />
                            Zip
                        </button>
                        <button
                            disabled={!isSingleZipSelected || isUnzipping}
                            onClick={handleUnzip}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-zinc-700 dark:text-gray-200 dark:hover:bg-zinc-700 transition-colors"
                        >
                            {isUnzipping ? (
                                <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                            ) : (
                                <ArchiveRestore className="w-4 h-4" />
                            )}
                            Unzip
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
                            onClick={() => setIsDeleteModalOpen(true)}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-zinc-800 dark:border-red-900/30 dark:text-red-400 dark:hover:bg-red-900/20 transition-colors"
                        >
                            <Trash2 className="w-4 h-4" />
                            Delete
                        </button>
                    </div>
                </>
            }
            {renderBreadcrumbs()}

            {error && (
                <div className="p-4 mb-6 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm border border-red-100 dark:border-red-900/30">
                    {error}
                </div>

            )}


            <div className="overflow-x-auto">
                {ctxMenuPosition && (
                    <div data-role="menu" className="absolute bg-white shadow-lg rounded-md border border-gray-200 w-40 py-1 z-50 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white" style={{ top: ctxMenuPosition.y, left: ctxMenuPosition.x }}>
                        <a
                            onClick={singleSelected ? openRenameModal : undefined}
                            className={`flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-200 dark:text-white rounded-md ${singleSelected ? 'cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                        >
                            <Edit2 className="w-4 h-4" /> Rename
                        </a>
                        <a
                            onClick={noneSelected ? undefined : () => setIsMoveModalOpen(true)}
                            className={`flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-200 dark:text-white rounded-md ${!noneSelected ? 'cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                        >
                            <MoveRight className="w-4 h-4" />Move
                        </a>
                        <a
                            onClick={noneSelected ? undefined : () => setIsZipModalOpen(true)}
                            className={`flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-200 dark:text-white rounded-md ${!noneSelected ? 'cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                        >
                            <FileArchive className="w-4 h-4" /> Zip
                        </a>
                        <a
                            onClick={!isSingleZipSelected ? undefined : handleUnzip}
                            className={`flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-200 dark:text-white rounded-md ${isSingleZipSelected ? 'cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                        >
                            <ArchiveRestore className="w-4 h-4" /> Unzip
                        </a>
                        <a
                            className={`flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-200 dark:text-white rounded-md ${!noneSelected ? 'cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                        >
                            <Download className="w-4 h-4" /> Download
                        </a>
                        <div className="h-px bg-slate-200 my-1"></div>
                        <a
                            onClick={noneSelected ? undefined : () => setIsDeleteModalOpen(true)}
                            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-md text-red-500 hover:bg-red-100 ${!noneSelected ? 'cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}>
                            <Trash2 className="w-4 h-4" /> Delete
                        </a>
                    </div>
                )}
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
                                    draggable
                                    onDragStart={(e) => handleDragStart(e, file.name)}
                                    onDragEnter={(e) => file.type === 'dir' && handleFolderDragEnter(e, file.name)}
                                    onDragLeave={(e) => file.type === 'dir' && handleFolderDragLeave(e, file.name)}
                                    onDragOver={(e) => handleDragOver(e, file.type === 'dir' ? file.name : undefined)}
                                    onDrop={(e) => handleDrop(e, file)}
                                    onClick={(e) => handleRowClick(e, file, idx)}
                                    onDoubleClick={() => handleDoubleClick(file)}
                                    className={`group transition-colors cursor-pointer ${
                                        dragOverFolder === file.name
                                            ? 'bg-indigo-100 dark:bg-indigo-900/40 outline-dashed outline-2 outline-indigo-400 -outline-offset-2'
                                            : selectedItems.has(file.name)
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
