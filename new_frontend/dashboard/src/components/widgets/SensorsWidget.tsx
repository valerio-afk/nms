import { Thermometer, Fan } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { HardwareSensor } from '../../types/dashboard';

interface SensorsWidgetProps {
    sensors: HardwareSensor[];
}

export default function SensorsWidget({ sensors }: SensorsWidgetProps) {
    const { t } = useTranslation();

    const temps = sensors.filter(s => s.type === 'temperature' || s.unit === '°C');
    const fans = sensors.filter(s => s.type === 'fan' || s.unit === 'RPM');

    return (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 flex flex-col justify-between transition-all hover:shadow-md">
            <div>
                <div className="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400">
                            <Thermometer className="w-5 h-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                                {t('widgets.sensors.title', 'Hardware Sensors')}
                            </h3>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {sensors.length} {t('widgets.sensors.normal', 'Monitors Active')}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="mt-4 space-y-2.5 max-h-56 overflow-y-auto pr-1">
                    {sensors.length === 0 ? (
                        <p className="text-xs text-gray-400 dark:text-zinc-500 py-4 text-center">
                            {t('widgets.sensors.no_sensors', 'No sensors detected or available')}
                        </p>
                    ) : (
                        sensors.map((sensor, idx) => {
                            const isTemp = sensor.type === 'temperature' || sensor.unit === '°C';
                            const isHighTemp = isTemp && sensor.value > 75;

                            return (
                                <div
                                    key={sensor.name + idx}
                                    className="flex items-center justify-between p-2.5 rounded-xl bg-gray-50 dark:bg-zinc-800/60 border border-gray-100 dark:border-zinc-800"
                                >
                                    <div className="flex items-center gap-2">
                                        {isTemp ? (
                                            <Thermometer className={`w-4 h-4 ${isHighTemp ? 'text-rose-500' : 'text-gray-400'}`} />
                                        ) : (
                                            <Fan className="w-4 h-4 text-sky-400 animate-spin" style={{ animationDuration: '3s' }} />
                                        )}
                                        <span className="text-xs font-semibold text-gray-800 dark:text-zinc-200 truncate">
                                            {sensor.name}
                                        </span>
                                    </div>

                                    <span
                                        className={`text-xs font-mono font-medium px-2 py-0.5 rounded-md ${
                                            isHighTemp
                                                ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-400 font-bold'
                                                : 'bg-gray-200/70 text-gray-800 dark:bg-zinc-700/60 dark:text-zinc-300'
                                        }`}
                                    >
                                        {sensor.value} {sensor.unit}
                                    </span>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>

            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-zinc-800/80 text-xs text-gray-500 dark:text-zinc-400 flex justify-between">
                <span>{t('widgets.sensors.temperature', 'Sensors')}</span>
                <span className="font-semibold text-gray-900 dark:text-white">
                    {temps.length} Temps / {fans.length} Fans
                </span>
            </div>
        </div>
    );
}
