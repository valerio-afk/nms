import {formatBytes} from '../utils/formats'

interface StorageBarProps {
  used: number; // e.g., 10
  total: number; // e.g., 20
}

const StorageBar = ({ used, total }: StorageBarProps) => {
  const percentage = Math.min((used / total) * 100, 100);

  return (
    <div className="w-full max-w-md">
      <div className="flex justify-between mb-1 text-sm font-medium text-gray-700 dark:text-white">
        <span>{formatBytes(used)} used</span>
        <span>{formatBytes(total)} total</span>
      </div>
      <div className="w-full h-4 bg-gray-200  dark:bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-4 bg-blue-500 dark:bg-blue-600 rounded-full"
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
};

export default StorageBar;