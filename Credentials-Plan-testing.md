CodeSentinal Test


I deployed this current project...

## The Vercel Frontend Link : https://code-sentinal-chi.vercel.app/
## The Render Backend Link : https://codesentinal-ty40.onrender.com/
## The GitHub Link : https://github.com/Anshul-777/CodeSentinal

you are to do a browser test on frontend, and see registration. If it shows error, You must Go to the backend and see if issue is in that, and if not there. Then visit GitHub and read all, connection and all and see where's the issue. 

0. The vercel environment is this : 
## VITE_API_URL=https://codesentinal-ty40.onrender.com/api/v1


Before i tell precise render, you must understand that. 

1. Render uses docker. 

I made Postgress (codesentinel-postgres), 
then Web service (CodeSentinal)
on render. 

## The Render Environment variable is this : 

ALLOWED_ORIGINS=["https://code-sentinal-chi.vercel.app","http://localhost:5173"]

APP_ENV=production

CELERY_BROKER_URL=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379

CELERY_RESULT_BACKEND=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379

DATABASE_URL=postgresql+asyncpg://codesentinel_user:ZqrXa1IRhEvgxYSMJtgknltqAYV5svsf@dpg-d7j0ph7lk1mc73a74ep0-a/codesentinel_prod

DEBUG=false

ENCRYPTION_KEY=z9fLrAnIkM8ah0tRlPR2i1BjU6Tx9Zhgqz4EN51EfDU=

FRONTEND_URL=https://code-sentinal-chi.vercel.app

GITHUB_APP_CLIENT_ID=Iv23li2OPXP07C473FQT

GITHUB_APP_CLIENT_SECRET=9e432893eaa9d8f402ef7516b8b49617931a8877

GITHUB_APP_ID=3440019

GITHUB_APP_NAME=codesentinel-devsecops

GITHUB_APP_PRIVATE_KEY=MIIEogIBAAKCAQEAtkT5rQH4oy+16d1Lb/E+WEDpXgJ7oZzMmZPPukIotzKNUgq8
+rcrrXHotVk9k4xz04m4ngFuNFiMVOJMAUALJonr6kekZSZGbIKc61rHp+wb+/cq
m/uF2W4h/HjnfArKAZWLP5bEvY9iv1K6QixMfTDo74+Yy6i1/ErxglUMM0VMD4cC
x0qWC2tInbogBpCyebmRnqP8mDmq775EMCWHshmGLZbZHzLxu/U2TRiD9QixmUDf
xTX0mkfWZqxRKnELe/tm7h2Pv9OM1F4eJsiNRn3wdcBXAsBVt6eC3nCzi226KjvW
CqLBjTC/lvbuqsWYGzmyNxzKk3vtlx78oiuVtQIDAQABAoIBAGNqZ8yHwLgxc8Wl
YFokeV7luOP/8rMJtUcnKixrnY2e0xompUES2431DXqsvDtYZmzBN6NnIFcI3TIH
ZHFiHzLcE4NrpC1PnSXeb/ynPTNIQ1NBU0pU/ILF4V+2CnzL3bbTfGoosBK8vJ2i
X9lsFCRMoyDXb/3Vfb2omuX9wXPMsqTRKakKBloWn7GjpJ6qqui4HaKfOkikXPm9
UEhAflENcQsU0HXn446PW4V/8NAYVqg4HxlxjQ56FwCP7kS5EMk1dZ6WRhv9zHbm
7u82bjKa7ZzqKhw2/9SSTe0oODF5ITAS3gXgxcdPFCuYANfhL+7YdAaIhWH+IciF
Vg1oYEECgYEA3R3Q3+bBitW7p3G3ETF7nFMFKyu6p+X/621M1jnUsGw9GliPL40Y
LCf1K3EFYzkFA0NtiWIKUXnuWXUutL/Eq24BJffjX8kwaxPuVD+HidCtR0YqC6hJ
tlU8cXTwfZK9DCATQFhFMvoO9nuaHhbn01p4/Ow66y+iU/qIa07elN0CgYEA0wZA
n+dP/58R3DXqATHCVGPmliAz4IVf78rnCbAgS5TItjHjhyzkzjY7wW6xEYXZjQPr
YHWzO2z04pOfn3LT+4vR9Nj62/Dv7hUmHGPbUovDvV5XAbqfNuYxAx8PysOOPe/j
pWdvRvyEO7PgJ/b7sPU7AiiS+wfBOTJuKFhA6rkCgYBQXeHpP2nhGEYYWhB7w0x2
SQZ75mz1UXdvDk77HhHb/btHtCB23AWJJwzJOU8H/VWBFiTd5jBx5KtpAFp1f63v
0Q/ByRNvYSSkBp59KIoO4TXZzfrCOexwxRIu+p3eRlNH8PCOVobwPErr84jUnuar
vxpyczoG+U060Lh8qDHmUQKBgBpgrbNPNrC9MX5VPurnTWM/GZOqctGd2mAe/MI5
QdAwyOX9VnOPKQqdvNpw+7E1CfyWgNWN4NmMxQ+NZGaJ8/V9hMEWXkUf2N3pxtnF
oaSv08fYAwg0S7KRE49QUqkFyMH1On9ybnZxGhZcZaiZNtznynh6meTHE2AS7bId
VgABAoGAKzhgHVW3LSvMT1WZenjiTTL58MtVn5RIxBTatjBwIFem62wV8SqAgmYY
Uop6AkNP/U5WsYzDreLfm2izOHvKS7DXBKM81RPuiYwLWaAZ7Tdd5yqQE7HECEQ5
Nb7X5jxrwB2iBtEJrglcUDq3c0egUFKpnJ9unniaM9HrYLVkJlU=

GITHUB_APP_WEBHOOK_SECRET=CodeSentinal-36790AI

GITHUB_WEBHOOK_URL=https://codesentinal-ty40.onrender.com/webhooks/github

JWT_SECRET_KEY=nw9f3vqFt41WjJSAhykdsG7BYIxaoRHP20LMeTVuNKXz5Z6pDQbcgmOU8lriEC

REDIS_URL=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379

SECRET_KEY=NJyLA1cYKxGFRnpVDtXoOs2iI80mUMklh53e9aqg4vfCE6QWwrHjdPBubST7Zz

VITE_API_URL=https://codesentinal-ty40.onrender.com/api/v1



2. Redis is using console.upstash.com
Redis (codesentinel-shared-redis), 
This was done because the render was asking for money for worker, and thus we decided to use hybrid approach of making the celery worker in railway for free and use the external connection with render. 
but it failed connection, thus we used this Redis upstash for public connection. 

## REDIS_URL="rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379"



3. Railway for celery worker (codesentinel-worker)
and did precise env. 

as explained in Redis, the connection with that render Redis was failing so we changed it with upstash Redis. and worked. 

## The Railway Environment variable is below :

APP_ENV=production

DEBUG=false

SECRET_KEY=NJyLA1cYKxGFRnpVDtXoOs2iI80mUMklh53e9aqg4vfCE6QWwrHjdPBubST7Zz

JWT_SECRET_KEY=nw9f3vqFt41WjJSAhykdsG7BYIxaoRHP20LMeTVuNKXz5Z6pDQbcgmOU8lriEC

ENCRYPTION_KEY=z9fLrAnIkM8ah0tRlPR2i1BjU6Tx9Zhgqz4EN51EfDU=

DATABASE_URL=postgresql://codesentinel_user:ZqrXa1IRhEvgxYSMJtgknltqAYV5svsf@dpg-d7j0ph7lk1mc73a74ep0-a.oregon-postgres.render.com/codesentinel_prod

REDIS_URL=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379?ssl_cert_reqs=required

CELERY_BROKER_URL=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379?ssl_cert_reqs=required

CELERY_RESULT_BACKEND=rediss://default:gQAAAAAAAZGhAAIocDJlYmZhM2EyMTdmNzI0NzMwOWJkYzMzNWJmNjhkYmU2NXAyMTAyODE3@golden-firefly-102817.upstash.io:6379?ssl_cert_reqs=required

GITHUB_APP_ID=3440019

GITHUB_APP_NAME=codesentinel-devsecops

GITHUB_APP_WEBHOOK_SECRET=CodeSentinal-36790AI

GITHUB_WEBHOOK_URL=https://codesentinal-ty40.onrender.com/webhooks/github

GITHUB_APP_CLIENT_ID=Iv23li2OPXP07C473FQT

GITHUB_APP_CLIENT_SECRET=9e432893eaa9d8f402ef7516b8b49617931a8877

GITHUB_APP_PRIVATE_KEY=MIIEogIBAAKCAQEAtkT5rQH4oy+16d1Lb/E+WEDpXgJ7oZzMmZPPukIotzKNUgq8

ALLOWED_ORIGINS=["https://code-sentinal-chi.vercel.app","http://localhost:5173"]





## Also Let me give you precise Connections from Render Postgress:

Internal Database URL=postgresql://codesentinel_user:ZqrXa1IRhEvgxYSMJtgknltqAYV5svsf@dpg-d7j0ph7lk1mc73a74ep0-a/codesentinel_prod

External Database URL=postgresql://codesentinel_user:ZqrXa1IRhEvgxYSMJtgknltqAYV5svsf@dpg-d7j0ph7lk1mc73a74ep0-a.oregon-postgres.render.com/codesentinel_prod

PSQL Command=PGPASSWORD=ZqrXa1IRhEvgxYSMJtgknltqAYV5svsf psql -h dpg-d7j0ph7lk1mc73a74ep0-a.oregon-postgres.render.com -U codesentinel_user codesentinel_prod

To verify if internal is not used. 

I cant think of anything i missed, if you need anything ask me. and solve this entire issue. 


ALL THREE ARE LIVE, I SEE NO ERROR. AND VERCEL USED THE VERCEL ENV AND IT'S NEWLY GIVEN URL IS ALSO DEPLOYED WITH RENDER AND RAILWAY AGAIN. BUT STILL THE REGISTRATION IS FAILING. SO WHAT DO YOU THINK, 
IS IT THE CODE NOT USING THIS NEW DEPLOYED URL'S AND API, 
OR IS IT THAT MY ENV HAS ISSUES EVEN THOUGH IT'S LIVE 
YOU CAN READ THE LOGS AND PLAN FILE TO UNDERSTAND WHAT WE DID........

WE STILL NEED TO MAKE THAT GITHUB APP CHANGES WITH THIS NEW DATA. YOU MAY LOOK AT IMAGES IF NEEDED. 
NOW PLEASE SOLVE THIS ISSUE LIKE YOU DID WITH FREELANCEOS. 