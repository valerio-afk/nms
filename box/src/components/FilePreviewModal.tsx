import { useState, useEffect } from 'react';
import { X, AlertCircle, Music } from 'lucide-react';
import { getChecksum, getPreviewToken, getPreviewUrl, type FileInfo } from '../utils/api';
import { formatBytes } from '../utils/formats';

interface FilePreviewModalProps {
    isOpen: boolean;
    onClose: () => void;
    file: FileInfo | null;
    currentPath: string;
}

export default function FilePreviewModal({ isOpen, onClose, file, currentPath }: FilePreviewModalProps) {
    const [checksum, setChecksum] = useState<string | null>(null);
    const [previewContent, setPreviewContent] = useState<{ type: 'text' | 'image' | 'video' | 'audio' | 'pdf' | 'error' | 'unsupported', data?: string | null }>({ type: 'unsupported' });
    const [loadingPreview, setLoadingPreview] = useState(false);

    useEffect(() => {
        let isMounted = true;

        if (isOpen && file) {
            const fullPath = currentPath ? `${currentPath}/${file.name}` : file.name;

            // Reset states
            setChecksum('calculating...');
            setPreviewContent({ type: 'unsupported' });
            setLoadingPreview(true);

            // Fetch checksum
            getChecksum(fullPath)
                .then(res => {
                    if (isMounted) setChecksum(res);
                })
                .catch(() => {
                    if (isMounted) setChecksum('Error calculating checksum');
                });

            // Fetch preview if applicable
            if (file.type === 'video' || file.type === 'text' || file.type === 'image' || file.type === 'audio' || file.type === 'pdf') {
                getPreviewToken(fullPath)
                    .then(async (previewToken) => {
                        if (!isMounted) return;
                        
                        const url = getPreviewUrl(fullPath, previewToken);

                        if (file.type === 'video' || file.type === 'image' || file.type === 'audio' || file.type === 'pdf') {
                            setPreviewContent({ type: file.type, data: url });
                        } else if (file.type === 'text') {
                            const res = await fetch(url);
                            if (!res.ok) throw new Error('Failed to fetch text preview');
                            const text = await res.text();
                            if (!isMounted) return;
                            setPreviewContent({ type: 'text', data: text });
                        }
                    })
                    .catch(err => {
                        console.error('Preview error:', err);
                        if (isMounted) {
                            setPreviewContent({ type: 'error', data: 'Preview not available or error fetching content.' });
                        }
                    })
                    .finally(() => {
                        if (isMounted) setLoadingPreview(false);
                    });
            } else {
                setLoadingPreview(false);
                setPreviewContent({ type: 'unsupported' });
            }
        }

        return () => {
            isMounted = false;
        };
    }, [isOpen, file, currentPath]);

    if (!isOpen || !file) return null;

    const fullPath = currentPath ? `${currentPath}/${file.name}` : file.name;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-gray-900/50 dark:bg-black/50 backdrop-blur-sm">
            <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl ring-1 ring-gray-900/5 dark:ring-white/10 w-full max-w-4xl max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-200">

                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-zinc-800">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate pr-4">
                        Preview: {file.name}
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-gray-500 hover:bg-gray-100 dark:hover:bg-zinc-800 p-1.5 rounded-lg transition-colors focus:outline-none"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Preview Content Area */}
                <div className="flex-1 overflow-auto p-6 bg-gray-50 dark:bg-black/20 flex flex-col items-center justify-center min-h-[300px]">
                    {loadingPreview ? (
                        <div className="flex flex-col items-center text-gray-500 dark:text-gray-400">
                            <div className="w-8 h-8 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
                            <p>Loading preview...</p>
                        </div>
                    ) : previewContent.type === 'image' && previewContent.data ? (
                        <img
                            src={previewContent.data}
                            alt={file.name}
                            className="max-w-full max-h-[60vh] object-contain rounded drop-shadow-md"
                        />
                    ) : previewContent.type === 'video' && previewContent.data ? (
                        <video
                            src={previewContent.data}
                            controls
                            autoPlay
                            className="max-w-full max-h-[60vh] bg-black rounded drop-shadow-md outline-none"
                        />
                    ) : previewContent.type === 'pdf' && previewContent.data ? (
                        <div className="w-full h-full flex flex-col bg-gray-100 dark:bg-zinc-800 rounded-lg overflow-hidden border border-gray-200 dark:border-zinc-700 min-h-[60vh]">
                            <iframe 
                                src={previewContent.data} 
                                className="w-full h-full flex-1 border-none"
                                title={file.name}
                            />
                        </div>
                    ) : previewContent.type === 'audio' && previewContent.data ? (
                        <div className="w-full max-w-sm p-8 bg-white dark:bg-zinc-800 rounded-2xl shadow-sm border border-gray-200 dark:border-zinc-700 flex flex-col items-center gap-6">
                            <div className="w-16 h-16 bg-indigo-50 dark:bg-indigo-900/30 rounded-full flex items-center justify-center">
                                <Music className="w-8 h-8 text-indigo-500" />
                            </div>
                            <audio 
                                src={previewContent.data} 
                                controls 
                                autoPlay
                                className="w-full outline-none"
                            />
                        </div>
                    ) : previewContent.type === 'text' && previewContent.data !== null ? (
                        <div className="w-full h-full text-left bg-white dark:bg-zinc-950 p-4 rounded-lg border border-gray-200 dark:border-zinc-800 shadow-sm overflow-auto max-h-[60vh]">
                            <pre className="text-sm font-mono text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words">
                                {previewContent.data}
                            </pre>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center text-gray-500 dark:text-gray-400">
                            <AlertCircle className="w-12 h-12 mb-3 opacity-50" />
                            <p>Preview not available</p>
                        </div>
                    )}
                </div>

                {/* Info Footer */}
                <div className="p-4 bg-white dark:bg-zinc-900 border-t border-gray-200 dark:border-zinc-800 rounded-b-xl flex flex-col gap-2 text-sm">
                    <div className="grid grid-cols-[100px_1fr] gap-x-4 items-center">
                        <span className="font-semibold text-gray-600 dark:text-gray-400">Location:</span>
                        <span className="text-gray-900 dark:text-gray-100 truncate">{fullPath}</span>
                    </div>
                    <div className="grid grid-cols-[100px_1fr] gap-x-4 items-center">
                        <span className="font-semibold text-gray-600 dark:text-gray-400">Size:</span>
                        <span className="text-gray-900 dark:text-gray-100">{formatBytes(file.size || 0)}</span>
                    </div>
                    <div className="grid grid-cols-[100px_1fr] gap-x-4 items-start">
                        <span className="font-semibold text-gray-600 dark:text-gray-400 mt-0.5">Checksum (MD5):</span>
                        <span className="text-gray-900 dark:text-gray-100 font-mono text-xs break-all bg-gray-100 dark:bg-zinc-800 px-2 py-1 rounded">
                            {checksum}
                        </span>
                    </div>
                </div>

            </div>
        </div>
    );
}
