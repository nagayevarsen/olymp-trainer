import { t } from './i18n'
// Название проекта меняется здесь (или переменной VITE_APP_NAME при сборке).
export const APP_NAME: string = import.meta.env.VITE_APP_NAME ?? 'olymp-trainer'
export const APP_TAGLINE = t('Олимпиадная математика и физика с ИИ-наставником')
