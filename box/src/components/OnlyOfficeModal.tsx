import { useState, useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { getOnlyOfficeConfig, getOnlyOfficeConfigShared, type FileInfo } from '../utils/api';

interface OnlyOfficeModalProps {
    isOpen: boolean;
    onClose: () => void;
    file: FileInfo | null;
    currentPath: string;
    shareToken?: string;
}

export default function OnlyOfficeModal({ isOpen, onClose, file, currentPath, shareToken }: OnlyOfficeModalProps) {
    const [config, setConfig] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const containerRef = useRef<HTMLDivElement>(null);
    const editorRef = useRef<any>(null);

    useEffect(() => {
        let isMounted = true;
        if (isOpen && file) {
            setLoading(true);
            setError(null);
            setConfig(null);
            let configPromise: Promise<any>;
            if (shareToken) {
                // Use the filesharing endpoint; path must be relative to the share root
                // (same logic as browseFileSharing — built from currentPath, never relative_path)
                const sharePath = currentPath ? `${currentPath}/${file.name}` : file.name;
                configPromise = getOnlyOfficeConfigShared(sharePath, shareToken);
            } else {
                const fullPath = ('relative_path' in file && (file as any).relative_path)
                    ? (file as any).relative_path
                    : (currentPath ? `${currentPath}/${file.name}` : file.name);
                configPromise = getOnlyOfficeConfig(fullPath);
            }
            configPromise.then(res => {
                if (isMounted) setConfig(res);
            }).catch(err => {
                console.error(err);
                if (isMounted) setError("Failed to load OnlyOffice configuration");
            }).finally(() => {
                if (isMounted) setLoading(false);
            });
        }
        return () => { isMounted = false; };
    }, [isOpen, file, currentPath]);

    useEffect(() => {
        if (!config || !containerRef.current) return;

        const scriptUrl = `${window.location.protocol}//${window.location.hostname}:8090/web-apps/apps/api/documents/api.js`;
        let script = document.querySelector(`script[src="${scriptUrl}"]`) as HTMLScriptElement;

        const initEditor = () => {
            if ((window as any).DocsAPI) {
                if (editorRef.current && editorRef.current.destroyEditor) {
                    editorRef.current.destroyEditor();
                    editorRef.current = null;
                }
                if (containerRef.current) {
                    containerRef.current.innerHTML = '<div id="onlyoffice-editor-container" style="width: 100%; height: 100%;"></div>';
                    editorRef.current = new (window as any).DocsAPI.DocEditor('onlyoffice-editor-container', config);
                }
            }
        };

        const handleLoad = () => initEditor();

        if (!script) {
            script = document.createElement('script');
            script.src = scriptUrl;
            script.onload = handleLoad;
            document.head.appendChild(script);
        } else if ((window as any).DocsAPI) {
            initEditor();
        } else {
            script.addEventListener('load', handleLoad);
        }

        return () => {
            if (script) {
                script.removeEventListener('load', handleLoad);
            }
            if (editorRef.current && editorRef.current.destroyEditor) {
                editorRef.current.destroyEditor();
                editorRef.current = null;
            }
            if (containerRef.current) {
                containerRef.current.innerHTML = '';
            }
        };
    }, [config]);

    if (!isOpen || !file) return null;

    return (
        <div className="fixed inset-0 z-[200] flex flex-col bg-gray-100 dark:bg-zinc-950">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-300 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm shrink-0">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate pr-4">
                    OnlyOffice: {file.name}
                </h3>
                <button
                    onClick={onClose}
                    className="text-gray-500 hover:bg-gray-100 dark:hover:bg-zinc-800 p-1.5 rounded-lg transition-colors focus:outline-none"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>
            
            {/* Content */}
            <div className="flex-1 w-full h-full relative overflow-hidden flex flex-col items-center justify-center">
                {loading && (
                    <div className="flex flex-col items-center text-gray-500 dark:text-gray-400">
                        <div className="w-8 h-8 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
                        <p>Loading OnlyOffice Editor...</p>
                    </div>
                )}
                {error && (
                    <div className="text-red-500 p-4">{error}</div>
                )}
                {config && (
                    <div ref={containerRef} className="w-full h-full absolute inset-0"></div>
                )}
            </div>
        </div>
    );
}
