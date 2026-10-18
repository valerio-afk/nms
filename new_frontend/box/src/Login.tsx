import { Login as SharedLogin, type LoginProps } from '@nms/shared';

export default function Login(props: LoginProps) {
    return <SharedLogin {...props} />;
}
