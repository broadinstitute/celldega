export const handleAsyncError = (error, context = {}) => {
  const {
    coordinates,
    url,
    messages = {},
    throwOnAuth = true,
    logUnexpected = true,
  } = context;

  const defaultMessages = {
    network: 'Network error occurred',
    notFound: 'Resource not found',
    unauthorized: 'Unauthorized access',
    forbidden: 'Access forbidden',
    unexpected: 'Unexpected error occurred',
  };

  const msgs = { ...defaultMessages, ...messages };

  // Network errors
  if (error.name === 'NetworkError' || error.code === 'NETWORK_ERROR') {
    return { error: 'network', message: msgs.network, retryable: true };
  }

  // Resource not found
  if (error.status === 404) {
    return { error: 'not_found', message: msgs.notFound, retryable: false };
  }

  // Authentication/Authorization
  if (error.status === 401) {
    const message = coordinates
      ? `${msgs.unauthorized} for resource at ${coordinates}`
      : msgs.unauthorized;

    if (throwOnAuth) {
      throw new Error(message);
    }
    return { error: 'unauthorized', message, retryable: false };
  }

  if (error.status === 403) {
    const message = coordinates
      ? `${msgs.forbidden} for resource at ${coordinates}`
      : msgs.forbidden;

    if (throwOnAuth) {
      throw new Error(message);
    }
    return { error: 'forbidden', message, retryable: false };
  }

  // Unexpected errors
  if (logUnexpected) {
    const logContext = {
      ...(coordinates && { coordinates }),
      ...(url && { url }),
      error: error.message,
      stack: error.stack,
    };
    console.error(msgs.unexpected, logContext);
  }

  return { error: 'unexpected', message: msgs.unexpected, retryable: false };
};

export const handleValidationWarning = (message, context = {}) => {
  const { logLevel = 'warn', shouldLog = true } = context;

  if (
    shouldLog &&
    (process.env.NODE_ENV === 'development' || context.forceLog)
  ) {
    console[logLevel](message, context.data || '');
  }
};
